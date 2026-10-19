import 'package:material_ui/material_ui.dart';
import 'package:intl/intl.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/models/member.dart';
import 'package:kitchenowl/models/task.dart';

/// Bottom sheet content to create or edit a [Task]. Pops with the edited task
/// or with [TaskEditSheet.deleted] if the user chose to delete it.
class TaskEditSheet extends StatefulWidget {
  static const deleted = Object();

  final Task task;
  final List<Member> members;
  final bool isNew;

  const TaskEditSheet({
    super.key,
    required this.task,
    required this.members,
    this.isNew = false,
  });

  @override
  State<TaskEditSheet> createState() => _TaskEditSheetState();
}

class _TaskEditSheetState extends State<TaskEditSheet> {
  late Task task;
  late final TextEditingController nameController;
  late final TextEditingController repeatController;

  @override
  void initState() {
    super.initState();
    task = widget.task;
    nameController = TextEditingController(text: task.name);
    repeatController = TextEditingController(
      text: task.repeatEvery?.toString() ?? '1',
    );
  }

  @override
  void dispose() {
    nameController.dispose();
    repeatController.dispose();
    super.dispose();
  }

  String _unitLabel(BuildContext context, String unit) {
    final l = AppLocalizations.of(context)!;
    switch (unit) {
      case 'week':
        return l.taskUnitWeek;
      case 'month':
        return l.taskUnitMonth;
      default:
        return l.taskUnitDay;
    }
  }

  bool get _isValid {
    if (nameController.text.trim().isEmpty) return false;
    if (task.hasRotation && task.participants.length < 2) return false;

    return true;
  }

  bool get _hasRepeat => task.recurring && task.dueDate != null;

  void _setRotation(String mode) {
    setState(() {
      var participants = task.participants;
      var assignedTo = task.assignedTo;
      if (mode == Task.rotationNone) {
        participants = const [];
      } else if (participants.isEmpty) {
        participants = widget.members.map((e) => e.id).toList();
      }
      if (mode != Task.rotationNone &&
          (assignedTo == null || !participants.contains(assignedTo))) {
        assignedTo = participants.firstOrNull;
      }
      task = task.copyWith(
        rotationMode: mode,
        participants: participants,
        assignedTo: Nullable(assignedTo),
      );
    });
  }

  void _toggleParticipant(int id, bool selected) {
    setState(() {
      final participants = List<int>.of(task.participants);
      if (selected) {
        participants.add(id);
      } else {
        participants.remove(id);
      }
      var assignedTo = task.assignedTo;
      if (!participants.contains(assignedTo)) {
        assignedTo = participants.firstOrNull;
      }
      task = task.copyWith(
        participants: participants,
        assignedTo: Nullable(assignedTo),
      );
    });
  }

  void _save() {
    var result = task.copyWith(name: nameController.text.trim());
    if (_hasRepeat) {
      final every = int.tryParse(repeatController.text) ?? 1;
      result = result.copyWith(
        repeatEvery: Nullable(every < 1 ? 1 : every),
        repeatUnit: Nullable(task.repeatUnit ?? 'week'),
      );
    } else {
      result = result.copyWith(
        repeatEvery: const Nullable(null),
        repeatUnit: const Nullable(null),
      );
    }
    Navigator.of(context).pop(result);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    final assignableMembers = task.hasRotation
        ? widget.members.where((m) => task.participants.contains(m.id))
        : widget.members;

    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.isNew ? l.taskNew : l.taskEdit,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: nameController,
              autofocus: widget.isNew,
              maxLength: 128,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(labelText: l.name),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 8),
            // assignment
            DropdownButtonFormField<int?>(
              value: assignableMembers.any((m) => m.id == task.assignedTo)
                  ? task.assignedTo
                  : null,
              decoration: InputDecoration(labelText: l.taskAssignee),
              items: [
                if (!task.hasRotation)
                  DropdownMenuItem<int?>(
                    value: null,
                    child: Text(l.taskUnassigned),
                  ),
                ...assignableMembers.map(
                  (m) => DropdownMenuItem<int?>(
                    value: m.id,
                    child: Text(m.name),
                  ),
                ),
              ],
              onChanged: (value) => setState(
                () => task = task.copyWith(assignedTo: Nullable(value)),
              ),
            ),
            const SizedBox(height: 16),
            // rotation
            Text(l.taskRotation, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              showSelectedIcon: false,
              segments: [
                ButtonSegment(
                  value: Task.rotationNone,
                  label: Text(l.taskRotationNone),
                ),
                ButtonSegment(
                  value: Task.rotationOrdered,
                  label: Text(l.taskRotationOrdered),
                ),
                ButtonSegment(
                  value: Task.rotationRandom,
                  label: Text(l.taskRotationRandom),
                ),
              ],
              selected: {task.rotationMode},
              onSelectionChanged: (s) => _setRotation(s.first),
            ),
            if (task.hasRotation) ...[
              const SizedBox(height: 8),
              Text(
                l.taskParticipants,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              Wrap(
                spacing: 8,
                children: widget.members
                    .map(
                      (m) => FilterChip(
                        label: Text(m.name),
                        selected: task.participants.contains(m.id),
                        onSelected: (v) => _toggleParticipant(m.id, v),
                      ),
                    )
                    .toList(),
              ),
              if (task.participants.length < 2)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    l.taskParticipantsMin,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
            ],
            const SizedBox(height: 16),
            // recurring + due date
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l.taskRecurring),
              value: task.recurring,
              onChanged: (v) => setState(
                () => task = task.copyWith(recurring: v),
              ),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l.taskDueDate),
              subtitle: Text(
                task.dueDate == null
                    ? l.taskNoDueDate
                    : DateFormat.yMMMd().format(task.dueDate!),
              ),
              trailing: task.dueDate == null
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear_rounded),
                      onPressed: () => setState(
                        () => task = task.copyWith(
                          dueDate: const Nullable(null),
                        ),
                      ),
                    ),
              onTap: () async {
                final now = DateTime.now();
                final picked = await showDatePicker(
                  context: context,
                  initialDate: task.dueDate ?? now,
                  firstDate: DateTime(now.year - 1),
                  lastDate: DateTime(now.year + 10),
                );
                if (picked != null) {
                  setState(
                    () => task = task.copyWith(dueDate: Nullable(picked)),
                  );
                }
              },
            ),
            if (_hasRepeat)
              Row(
                children: [
                  Expanded(child: Text(l.taskRepeatEvery)),
                  SizedBox(
                    width: 64,
                    child: TextField(
                      controller: repeatController,
                      keyboardType: TextInputType.number,
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(width: 12),
                  DropdownButton<String>(
                    value: task.repeatUnit ?? 'week',
                    items: Task.units
                        .map(
                          (u) => DropdownMenuItem(
                            value: u,
                            child: Text(_unitLabel(context, u)),
                          ),
                        )
                        .toList(),
                    onChanged: (u) => setState(
                      () => task = task.copyWith(repeatUnit: Nullable(u)),
                    ),
                  ),
                ],
              ),
            const SizedBox(height: 16),
            Row(
              children: [
                if (!widget.isNew)
                  TextButton(
                    onPressed: () =>
                        Navigator.of(context).pop(TaskEditSheet.deleted),
                    child: Text(
                      l.delete,
                      style:
                          TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ),
                const Spacer(),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(l.cancel),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _isValid ? _save : null,
                  child: Text(l.save),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
