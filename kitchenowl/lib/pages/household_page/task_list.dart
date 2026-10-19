import 'package:collection/collection.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import 'package:kitchenowl/cubits/auth_cubit.dart';
import 'package:kitchenowl/cubits/household_cubit.dart';
import 'package:kitchenowl/cubits/task_list_cubit.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/models/member.dart';
import 'package:kitchenowl/models/task.dart';
import 'package:kitchenowl/services/api/task.dart';
import 'package:kitchenowl/widgets/task_edit_sheet.dart';

/// Overdue first, then by due date, then own tasks, then alphabetical.
/// Tasks without a due date follow the dated ones.
List<Task> sortTasks(List<Task> tasks, int? myId) {
  final sorted = List<Task>.of(tasks);
  sorted.sort((a, b) {
    final aDate = a.dueDate;
    final bDate = b.dueDate;
    if (aDate != null && bDate != null) {
      final c = aDate.compareTo(bDate);
      if (c != 0) return c;
    } else if (aDate != null) {
      return -1;
    } else if (bDate != null) {
      return 1;
    }
    final aMine = a.assignedTo != null && a.assignedTo == myId;
    final bMine = b.assignedTo != null && b.assignedTo == myId;
    if (aMine != bMine) return aMine ? -1 : 1;

    return a.name.toLowerCase().compareTo(b.name.toLowerCase());
  });

  return sorted;
}

Future<void> showTaskEditSheet(
  BuildContext context, {
  Task? task,
}) async {
  final cubit = BlocProvider.of<TaskListCubit>(context);
  final members =
      BlocProvider.of<HouseholdCubit>(context).state.household.member ??
          const <Member>[];
  final result = await showModalBottomSheet<Object>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) => TaskEditSheet(
      task: task ?? const Task(),
      members: members,
      isNew: task == null,
    ),
  );
  if (result == null) return;
  if (result == TaskEditSheet.deleted && task != null) {
    await cubit.delete(task);
  } else if (result is Task) {
    if (task == null) {
      await cubit.add(result);
    } else {
      await cubit.update(result);
    }
  }
}

class TaskListPage extends StatelessWidget {
  const TaskListPage({super.key});

  Future<void> _markDone(BuildContext context, Task task) async {
    final l = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    final cubit = BlocProvider.of<TaskListCubit>(context);
    final confirmed = await askForConfirmation(
      context: context,
      title: Text(task.name),
      content: Text(l.taskMarkDone),
      confirmText: l.done,
    );
    if (!confirmed) return;
    final res = await cubit.done(task);
    switch (res) {
      case TaskDoneResult.ok:
        break;
      case TaskDoneResult.conflict:
        messenger.showSnackBar(SnackBar(content: Text(l.taskDoneConflict)));
        break;
      case TaskDoneResult.forbidden:
        messenger.showSnackBar(SnackBar(content: Text(l.taskDoneForbidden)));
        break;
      case TaskDoneResult.error:
        messenger.showSnackBar(SnackBar(content: Text(l.error)));
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    final cubit = BlocProvider.of<TaskListCubit>(context);
    final myId = BlocProvider.of<AuthCubit>(context).getUser()?.id;

    return SafeArea(
      child: RefreshIndicator(
        onRefresh: cubit.refresh,
        child: BlocBuilder<HouseholdCubit, HouseholdState>(
          builder: (context, householdState) =>
              BlocBuilder<TaskListCubit, TaskListCubitState>(
            builder: (context, state) {
              final members =
                  householdState.household.member ?? const <Member>[];
              final tasks = sortTasks(state.tasks, myId);

              return CustomScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 8, 0),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              l.tasks,
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                          ),
                          FilterChip(
                            label: Text(l.taskShowCompleted),
                            selected: state.showCompleted,
                            onSelected: cubit.setShowCompleted,
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (state is LoadingTaskListCubitState)
                    const SliverFillRemaining(
                      hasScrollBody: false,
                      child: Center(child: CircularProgressIndicator()),
                    )
                  else if (tasks.isEmpty)
                    SliverFillRemaining(
                      hasScrollBody: false,
                      child: Center(child: Text(l.taskNoTasks)),
                    )
                  else
                    SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (context, i) {
                          final task = tasks[i];
                          final assignee = members
                              .firstWhereOrNull((m) => m.id == task.assignedTo);
                          final parts = <String>[
                            assignee?.name ?? l.taskUnassigned,
                            if (task.dueDate != null)
                              DateFormat.yMMMd().format(task.dueDate!),
                          ];

                          return ListTile(
                            title: Text(task.name),
                            subtitle: Text(parts.join(' · ')),
                            leading: Icon(
                              task.recurring
                                  ? Icons.repeat_rounded
                                  : Icons.check_circle_outline_rounded,
                            ),
                            trailing: task.isOverdue
                                ? Chip(
                                    label: Text(l.taskOverdue),
                                    backgroundColor: Theme.of(context)
                                        .colorScheme
                                        .errorContainer,
                                  )
                                : null,
                            onTap: () => showTaskEditSheet(context, task: task),
                            onLongPress: task.isCompleted
                                ? () => cubit.reopen(task)
                                : () => _markDone(context, task),
                          );
                        },
                        childCount: tasks.length,
                      ),
                    ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
