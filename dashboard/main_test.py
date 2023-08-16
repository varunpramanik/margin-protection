# Copyright 2023 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for main.py."""
import datetime
import enum
import io
import re
import textwrap
import types
from typing import Optional
import uuid

from googleapiclient import discovery
import pandas as pd
import pytest

from launch_monitor.dashboard import main

CREDENTIALS = uuid.uuid4()


@pytest.fixture(autouse=True)
def before(monkeypatch):
  def fake_discovery(service, version, credentials):
    return types.SimpleNamespace(
        service=service, version=version, credentials=credentials
    )

  with monkeypatch.context() as m:
    m.setattr(discovery, 'build', fake_discovery)
    yield


def test_fill_dataframe():
  date = pd.to_datetime(
      '2020-01-01T00:00:00.000Z', format='%Y-%m-%dT%H:%M:%S.%f%z'
  )
  columns = {
      'Date': [date] * 2,
      'Category': pd.Series(['category'] * 2, dtype='string'),
      'Sheet_ID': pd.Series(['sheet_id'] * 2, dtype='string'),
      'Label': pd.Series(['label'] * 2, dtype='string'),
  }
  original = {'A': ['A1', 'A2'], 'B': ['B1', 'B2']}
  expected_result = pd.DataFrame({
      'Date': columns['Date'],
      'Category': pd.Series(['category'] * 2, dtype='string'),
      'Sheet_ID': columns['Sheet_ID'],
      'Label': columns['Label'],
      'A': original['A'],
      'B': original['B'],
  })

  result = main.fill_dataframe(
      pd.DataFrame.from_records(original),
      main.ReportName.with_filename(
          'category_label_rule_sheet_id_2020-01-01T00:00:00.000Z.csv'
      ),
  )

  pd.testing.assert_frame_equal(expected_result, result)


def test_load_data_into_pandas():
  fd = io.BytesIO()
  fd.seek(0)
  expected = pd.DataFrame(
      {'colA': ['A1', 'A2'], 'colB': ['B1', 'B2'], 'colC': ['C1', 'C2']},
      dtype='string',
  )

  actual = main.load_data_into_pandas(
      FakeRequest(
          fd,
          textwrap.dedent("""\
  colA,colB,colC
  A1,B1,C1
  A2,B2,C2""").encode('utf-8'),
      )
  )

  pd.testing.assert_frame_equal(actual, expected)


class TestReportName:

  def test_happy_simple(self):
    report_name = main.ReportName.with_filename(
        'abc_def_ghi_jkl_2000-01-01T00:00:00.000Z.csv'
    )
    assert report_name == main.ReportName(
        filename='abc_def_ghi_jkl_2000-01-01T00:00:00.000Z.csv',
        category='abc',
        label='def',
        rule='ghi',
        sheet_id='jkl',
        date=datetime.datetime(
            2000, 1, 1, 0, 0, 0, 0, tzinfo=datetime.timezone.utc
        ),
    )

  def test_happy_complex(self):
    report_name = main.ReportName.with_filename(
        '1abc_2def_3ghi_4jkl_underscored_id5_2000-01-01T00:00:00.000Z.csv'
    )
    assert report_name == main.ReportName(
        filename=(
            '1abc_2def_3ghi_4jkl_underscored_id5_2000-01-01T00:00:00.000Z.csv'
        ),
        category='1abc',
        label='2def',
        rule='3ghi',
        sheet_id='4jkl_underscored_id5',
        date=datetime.datetime(
            2000, 1, 1, 0, 0, 0, 0, tzinfo=datetime.timezone.utc
        ),
    )

  def test_happy_no_label(self):
    report_name = main.ReportName.with_filename(
        'abc__ghi_jkl_2000-01-01T00:00:00.000Z.csv'
    )
    assert not report_name.label

  @pytest.mark.parametrize(
      'filename',
      [
          'abc.csv',
          'abc_def_ghi_2000-01-01T00:00:00.000Z',
          'abc_def_ghi_jkl_2000-01-01T00:00:00.000Z',
          'abc_def_2000-01-01T00:00:00.000Z',
      ],
  )
  def test_sad(self, filename):
    with pytest.raises(ValueError) as exc:
      main.ReportName.with_filename(filename)

    assert str(exc.value).startswith('Invalid filename')


class TestGetLaunchMonitorFiles:

  def test_happy_no_time(self):
    drive = FakeDrive(error=False)
    files = main.get_latest_launch_monitor_files(
        drive, drive_id='parent_id', since=pd.NaT
    )
    assert len(files) == 4

  def test_happy_since_time2(self):
    drive = FakeDrive(error=False, since=Since.SECOND)
    files = main.get_latest_launch_monitor_files(
        drive, drive_id='parent_id', since=Since.SECOND.value
    )
    assert len(files) == 2

  def test_sad(self):
    drive = FakeDrive(error=True)

    with pytest.raises(ValueError) as exc:
      main.get_latest_launch_monitor_files(
          drive, drive_id='parent_id', since=Since.SECOND.value
      )

    assert str(exc.value).startswith(
        'No folder in drive with ID parent_id named "reports".'
    )


class FakeRequest:
  """Wraps a CSV file handler to simulate an `http.HttpRequest` for testing."""

  def __init__(self, fd, csv: bytes):
    self._fd = fd
    self.csv = csv.strip()
    self.uri = 'localhost'
    self.headers = {}
    self.http = FakeHttp(self.csv)

  def next_chunk(self):
    self._fd.write(self.csv)
    return 200, True


class FakeHttp:
  """Stubs an HTTP request for testing."""

  def __init__(self, csv: bytes):
    self.csv = csv
    self.response = FakeResponse()

  def request(self, *unused_args, **unused_kwargs):
    """Returns a `FakeResponse` and the CSV provided on class init."""
    return self.response, self.csv


class FakeResponse(dict):

  def __init__(self):
    self.status = 200
    super().__init__()


class Since(enum.Enum):
  """Defines some dates to test `FakeDrive` list queries."""

  def request(self, *unused_args, **unused_kwargs):
    return self.response, self.csv


class Since(enum.Enum):
  FIRST = datetime.datetime(
      2022, 1, 1, 0, 0, 0, 0, tzinfo=datetime.timezone.utc
  )
  SECOND = datetime.datetime(
      2023, 1, 1, 0, 0, 0, 0, tzinfo=datetime.timezone.utc
  )


class FakeDrive:
  """Mocks a Drive API's files() method to help test main.py functionality."""

  _file_list = [{'id': f'file{i}', 'name': 'File {i}'} for i in range(0, 4)]

  def __init__(self, error: bool = False, since: Optional[Since] = None):
    """Initializes a fake of a Drive API for testing.

    Args:
      error: If true, will always return an empty file list. Default false.
      since: A datetime.datetime object limiting when a file should be retrieved
        by. Used to mock the `" and createdTime>={createdTime}"` portion of a
        Drive query. This is omitted if the datetime is of type pandas.NaT.
    """
    self._error = error
    if since:
      since_string = datetime.datetime.strftime(
          since.value, '%Y-%m-%dT%H:%M:%S.%f%z'
      )
      self._and_time = f' and createdTime>="{since_string}"'
    else:
      self._and_time = ''
    file_map = {
        Since.FIRST: 1,
        Since.SECOND: 2,
    }
    self._file_index = file_map.get(since, 0)

  def files(self):
    return FakeDrive._Files(
        error=self._error, file_index=self._file_index, and_time=self._and_time
    )

  class _Files:
    """Stubs files() methods for testing main.py functions."""

    def __init__(self, error: bool, file_index: int, and_time: str):
      self.error = error
      self.file_index = file_index
      self.and_time = and_time

    def list(self, q: str):
      """Returns the execute function for Drive.files().list()."""
      matching = re.fullmatch(r"'([^']+)' in parents and name='reports'", q)

      def execute():
        if matching:
          if self.error:
            return {'files': []}
          return {'files': [{'id': 'abc'}]}
        elif q == f"'abc' in parents{self.and_time}":
          return {'files': FakeDrive._file_list[self.file_index :]}

      return types.SimpleNamespace(execute=execute)
