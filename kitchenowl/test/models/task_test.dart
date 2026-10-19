import 'package:flutter_test/flutter_test.dart';
import 'package:kitchenowl/models/nullable.dart';
import 'package:kitchenowl/models/task.dart';
import 'package:kitchenowl/pages/household_page/task_list.dart';

void main() {
  test("Task should de-/serialize", () {
    final task = Task(
      id: 3,
      name: "Dishes",
      recurring: true,
      dueDate: DateTime(2026, 3, 5),
      repeatEvery: 2,
      repeatUnit: 'week',
      rotationMode: Task.rotationOrdered,
      assignedTo: 1,
      participants: const [1, 2],
    );
    final actual = Task.fromJson(task.toJsonWithId());
    expect(actual, equals(task));
  });
  test("Task due date is a calendar day independent of the timezone", () {
    final json = Task(name: "x", dueDate: DateTime(2026, 12, 31)).toJson();
    expect(
      json["due_date"],
      equals(DateTime.utc(2026, 12, 31).millisecondsSinceEpoch),
    );
  });
  test("Task copyWith can clear nullable fields", () {
    final task = Task(name: "x", dueDate: DateTime(2026, 1, 1), assignedTo: 2);
    final cleared = task.copyWith(
      dueDate: const Nullable<DateTime>(null),
      assignedTo: const Nullable<int>(null),
    );
    expect(cleared.dueDate, isNull);
    expect(cleared.assignedTo, isNull);
  });
  test("Task is overdue only with a past due date", () {
    final now = DateTime.now();
    final yesterday = DateTime(now.year, now.month, now.day - 1);
    final today = DateTime(now.year, now.month, now.day);
    expect(Task(name: "x", dueDate: yesterday).isOverdue, isTrue);
    expect(Task(name: "x", dueDate: today).isOverdue, isFalse);
    expect(Task(name: "x").isOverdue, isFalse);
  });
  test("sortTasks: dated first, then own tasks, then alphabetical", () {
    final tasks = [
      Task(id: 1, name: "b"),
      Task(id: 2, name: "a", assignedTo: 9),
      Task(id: 3, name: "c", assignedTo: 7),
      Task(id: 4, name: "z", dueDate: DateTime(2026, 5, 1)),
      Task(id: 5, name: "y", dueDate: DateTime(2026, 1, 1)),
    ];
    expect(
      sortTasks(tasks, 7).map((e) => e.id).toList(),
      equals([5, 4, 3, 2, 1]),
    );
  });
}
