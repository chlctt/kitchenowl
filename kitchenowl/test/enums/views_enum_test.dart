import 'package:flutter_test/flutter_test.dart';
import 'package:kitchenowl/enums/views_enum.dart';

void main() {
  test("tasks is the second view and more the last", () {
    expect(ViewsEnum.values[1], equals(ViewsEnum.tasks));
    expect(ViewsEnum.values.last, equals(ViewsEnum.more));
  });
  test("addMissing keeps a complete ordering unchanged", () {
    final ordering = [
      ViewsEnum.items,
      ViewsEnum.tasks,
      ViewsEnum.recipes,
      ViewsEnum.planner,
      ViewsEnum.balances,
      ViewsEnum.more,
    ];
    expect(ViewsEnum.addMissing(ordering), equals(ordering));
  });
  test("addMissing inserts tasks behind items for existing households", () {
    // ordering stored before the tasks view existed (without more)
    final stored = [
      ViewsEnum.items,
      ViewsEnum.recipes,
      ViewsEnum.planner,
      ViewsEnum.balances,
    ];
    expect(
      ViewsEnum.addMissing(stored),
      equals([
        ViewsEnum.items,
        ViewsEnum.tasks,
        ViewsEnum.recipes,
        ViewsEnum.planner,
        ViewsEnum.balances,
        ViewsEnum.more,
      ]),
    );
  });
  test("addMissing respects a reordered list", () {
    final stored = [
      ViewsEnum.recipes,
      ViewsEnum.items,
      ViewsEnum.balances,
      ViewsEnum.planner,
    ];
    expect(
      ViewsEnum.addMissing(stored),
      equals([
        ViewsEnum.recipes,
        ViewsEnum.items,
        ViewsEnum.tasks,
        ViewsEnum.balances,
        ViewsEnum.planner,
        ViewsEnum.more,
      ]),
    );
  });
  test("addMissing puts a view without any predecessor first", () {
    expect(
      ViewsEnum.addMissing([ViewsEnum.recipes]).first,
      equals(ViewsEnum.items),
    );
  });
  test("addMissing keeps more last even if stored earlier", () {
    final result = ViewsEnum.addMissing([ViewsEnum.more, ViewsEnum.items]);
    expect(result.last, equals(ViewsEnum.more));
    expect(result.where((e) => e == ViewsEnum.more).length, equals(1));
  });
  test("parse knows tasks", () {
    expect(ViewsEnum.parse("tasks"), equals(ViewsEnum.tasks));
  });
}
