// ignore_for_file: prefer_const_constructors
import 'package:flutter_test/flutter_test.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/models/nullable.dart';

void main() {
  test("Item should be equal", () {
    // Given
    final c1 = Item(id: 1, name: "Name", ordering: 1);
    final c2 = Item(id: 1, name: "Name", ordering: 1);
    // Then
    expect(c1 == c2, equals(true));
  });
  test("Item should not be equal", () {
    // Given
    final c1 = Item(id: 1, name: "Name", ordering: 1);
    final c2 = Item(id: 1, name: "Name", ordering: 3);
    // Then
    expect(c1 == c2, equals(false));
  });
  test("Item should de-/serialize", () {
    // Given
    final c = Item(id: 1, name: "Name", ordering: 1);
    // When
    final actual = Item.fromJson(c.toJsonWithId());
    // Then
    expect(actual, equals(c));
  });

  test("ShoppinglistItem keeps assignee and due date across de-/serialize", () {
    final c = ShoppinglistItem(
      id: 1,
      name: "Milk",
      ordering: 1,
      assignedToId: 7,
      dueDate: DateTime(2026, 9, 15),
    );

    final actual = ShoppinglistItem.fromJson(c.toJsonWithId());

    expect(actual.assignedToId, equals(7));
    expect(actual.dueDate, equals(DateTime(2026, 9, 15)));
  });

  test("ShoppinglistItem.copyWith can clear assignee and due date", () {
    final c = ShoppinglistItem(
      id: 1,
      name: "Milk",
      assignedToId: 7,
      dueDate: DateTime(2026, 9, 15),
    );

    final cleared = c.copyWith(
      assignedToId: const Nullable(null),
      dueDate: const Nullable(null),
    );

    expect(cleared.assignedToId, isNull);
    expect(cleared.dueDate, isNull);
  });
}
