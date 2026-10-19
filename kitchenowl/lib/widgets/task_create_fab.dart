import 'package:material_ui/material_ui.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/pages/household_page/task_list.dart';

class TaskCreateFab extends StatelessWidget {
  const TaskCreateFab({super.key});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      tooltip: AppLocalizations.of(context)!.taskNew,
      onPressed: () => showTaskEditSheet(context),
      child: const Icon(Icons.add_rounded),
    );
  }
}
