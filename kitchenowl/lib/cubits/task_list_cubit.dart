import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/models/task.dart';
import 'package:kitchenowl/services/api/api_service.dart';
import 'package:kitchenowl/services/api/task.dart';

class TaskListCubit extends Cubit<TaskListCubitState> {
  final Household household;
  bool _refreshLock = false;

  TaskListCubit(this.household) : super(const LoadingTaskListCubitState()) {
    refresh();
  }

  Future<void> refresh() async {
    if (_refreshLock) return;
    _refreshLock = true;
    try {
      final showCompleted = state.showCompleted;
      final tasks = await ApiService.getInstance()
          .getTasks(household, completed: showCompleted);
      if (isClosed) return;
      emit(LoadedTaskListCubitState(
        tasks: tasks ?? const [],
        showCompleted: showCompleted,
        failed: tasks == null,
      ));
    } finally {
      _refreshLock = false;
    }
  }

  Future<void> setShowCompleted(bool value) async {
    emit(LoadingTaskListCubitState(showCompleted: value));
    await refresh();
  }

  Future<bool> add(Task task) async {
    final res = await ApiService.getInstance().addTask(household, task);
    await refresh();

    return res;
  }

  Future<bool> update(Task task) async {
    final res = await ApiService.getInstance().updateTask(task);
    await refresh();

    return res;
  }

  Future<bool> reopen(Task task) async {
    final res =
        await ApiService.getInstance().updateTask(task, completed: false);
    await refresh();

    return res;
  }

  Future<bool> delete(Task task) async {
    final res = await ApiService.getInstance().deleteTask(task);
    await refresh();

    return res;
  }

  Future<TaskDoneResult> done(Task task) async {
    final res = await ApiService.getInstance().doneTask(task);
    await refresh();

    return res;
  }
}

abstract class TaskListCubitState extends Equatable {
  final List<Task> tasks;
  final bool showCompleted;
  final bool failed;

  const TaskListCubitState({
    this.tasks = const [],
    this.showCompleted = false,
    this.failed = false,
  });

  @override
  List<Object?> get props => [tasks, showCompleted, failed];
}

class LoadingTaskListCubitState extends TaskListCubitState {
  const LoadingTaskListCubitState({super.showCompleted});
}

class LoadedTaskListCubitState extends TaskListCubitState {
  const LoadedTaskListCubitState({
    required super.tasks,
    super.showCompleted,
    super.failed,
  });
}
