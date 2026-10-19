import 'dart:convert';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/models/task.dart';
import 'package:kitchenowl/services/api/api_service.dart';

enum TaskDoneResult { ok, conflict, forbidden, error }

extension TaskApi on ApiService {
  static const baseRoute = '/tasks';

  Future<List<Task>?> getTasks(
    Household household, {
    bool completed = false,
  }) async {
    final res = await get(
      '${householdPath(household)}$baseRoute?completed=$completed',
    );
    if (res.statusCode != 200) return null;

    return List.from(jsonDecode(res.body))
        .map((e) => Task.fromJson(e))
        .toList();
  }

  Future<bool> addTask(Household household, Task task) async {
    final res = await post(
      '${householdPath(household)}$baseRoute',
      jsonEncode(task.toJson()),
    );

    return res.statusCode == 200;
  }

  Future<bool> updateTask(Task task, {bool? completed}) async {
    final res = await post(
      '$baseRoute/${task.id}',
      jsonEncode(task.toJson()
        ..addAll({if (completed != null) 'completed': completed})),
    );

    return res.statusCode == 200;
  }

  Future<bool> deleteTask(Task task) async {
    final res = await delete('$baseRoute/${task.id}');

    return res.statusCode == 200;
  }

  Future<TaskDoneResult> doneTask(Task task) async {
    final now = DateTime.now();
    final res = await post(
      '$baseRoute/${task.id}/done',
      jsonEncode({
        "expected_assigned_to": task.assignedTo,
        "done_on":
            DateTime.utc(now.year, now.month, now.day).millisecondsSinceEpoch,
      }),
    );
    switch (res.statusCode) {
      case 200:
        return TaskDoneResult.ok;
      case 409:
        return TaskDoneResult.conflict;
      case 403:
        return TaskDoneResult.forbidden;
      default:
        return TaskDoneResult.error;
    }
  }
}
