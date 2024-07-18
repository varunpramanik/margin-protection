/**
 * @license
 * Copyright 2024 Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {
  buildQuery,
  CamelCase,
  DotsToObject,
  ReportInterface,
} from "common/ads_api_types";

type AssertSubtype<TestType, End> = End extends TestType ? true : false;

type AssertEqual<TestType, End> = End extends TestType
  ? TestType extends End
    ? true
    : false
  : false;

describe("Ads API Types", () => {
  const CHILD_QUERY1 = buildQuery({
    queryParams: ["b"],
    queryFrom: "test",
  });
  const CHILD_QUERY2 = buildQuery({
    queryParams: ["c"],
    queryFrom: "test",
  });
  class ChildReport1 implements ReportInterface<typeof CHILD_QUERY1, "a"> {
    static output = ["a"];
    static query = CHILD_QUERY1;
    static key = "Child1";
    fetch() {
      return {};
    }

    transform(reportRow: { b: string }) {
      return ["a", { a: "a" }] as [string, { a: string }];
    }
  }
  class ChildReport2 implements ReportInterface<typeof CHILD_QUERY2, "b"> {
    static output = ["b"];
    static query = CHILD_QUERY2;
    static key = "Child2";
    fetch() {
      return {};
    }

    transform(reportRow: { c: string }) {
      return ["a", { b: "b" }] as [string, { b: string }];
    }
  }
  it("adjusts underscores to camel cases", () => {
    const test1: AssertEqual<CamelCase<"my_underscore">, "myUnderscore"> = true;
    expect(test1).toBeDefined();
  });

  it("does not camel case where not necessary", () => {
    // tslint:disable-next-line:ban-ts-suppressions
    // @ts-expect-error This type should not Assert<> to true.
    const test1: AssertEqual<CamelCase<"myunderscore">, "myUnderscore"> = true;
    expect(test1).toBeDefined();
  });

  it("handles dot notation", () => {
    const test1: AssertSubtype<
      DotsToObject<"my.dot_notation.works_well">,
      {
        my: { dotNotation: { worksWell: "" } };
      }
    > = true;
    expect(test1).toBeDefined();
  });

  it("handles blanks", () => {
    // tslint:disable:no-any
    const test1: AssertEqual<DotsToObject<any>, {}> = true;
    // tslint:disable-next-line:ban-ts-suppressions
    // @ts-expect-error This type should not Assert<> to true.
    const test2: AssertEqual<DotsToObject<any>, { "": "" }> = true;
    [test1, test2].forEach((test) => expect(test).toBeDefined());
    // tslint:enable:no-any
  });

  it("infers types from Report", () => {
    const request = buildQuery({
      queryParams: ["a_b_c.def", "b"],
      queryFrom: "test",
      joins: {
        "aBC.def": ChildReport1,
        b: ChildReport2,
      },
    });

    const test1: AssertSubtype<
      typeof request.joins,
      {
        "aBC.def": typeof ChildReport1;
        b: typeof ChildReport2;
      }
    > = true;
    const test2: AssertSubtype<
      typeof request.joins,
      {
        c: typeof ChildReport2;
        b: typeof ChildReport2;
      }
    > = false;
    // tslint:disable-next-line:ban-ts-suppressions
    // @ts-expect-error This type should not Assert<> to true.
    const test3: AssertSubtype<
      typeof request.joins,
      {
        bad1: typeof ChildReport2;
        bad2: typeof ChildReport2;
      }
    > = true;
    // tslint:disable-next-line:ban-ts-suppressions
    // @ts-expect-error This type should not Assert<> to false.
    const test4: AssertSubtype<
      typeof request.joins,
      {
        "aBC.def": typeof ChildReport1;
        b: typeof ChildReport2;
      }
    > = false;

    [test1, test2, test3, test4].forEach((test) => expect(test).toBeDefined());
  });
});
