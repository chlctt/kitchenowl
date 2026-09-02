import 'package:material_ui/material_ui.dart';
import 'package:intl/intl.dart';
import 'package:kitchenowl/cubits/household_cubit.dart';
import 'package:kitchenowl/helpers/build_context_extension.dart';
import 'package:kitchenowl/item_icons.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/models/member.dart';
import 'package:kitchenowl/widgets/selectable_button_card.dart';
import 'package:kitchenowl/widgets/selectable_button_list_tile.dart';
import 'package:kitchenowl/widgets/user_circle_avatar.dart';

class ShoppingItemWidget<T extends Item> extends StatelessWidget {
  final T item;
  final void Function(T)? onPressed;
  final void Function(T)? onLongPressed;
  final bool selected;
  final Widget? extraOption;

  /// Only applicable if gridStyle = false, raises the list items and makes them fully opaque.
  /// defaults to true for item is ShoppinglistItem || item is RecipeItem && selected
  final bool? raised;
  final bool gridStyle;
  final ListStyle listStyle;

  const ShoppingItemWidget({
    super.key,
    required this.item,
    this.onPressed,
    this.onLongPressed,
    this.selected = false,
    this.gridStyle = true,
    this.listStyle = ListStyle.cards,
    this.raised,
    this.extraOption,
  });

  /// Whether the item has a purchase date that still lies in the future.
  bool get _dueInFuture {
    final item = this.item;
    if (item is! ShoppinglistItem || item.dueDate == null) return false;
    final due = item.dueDate!;
    final today = DateTime.now();
    final dueDay = DateTime(due.year, due.month, due.day);
    final todayDay = DateTime(today.year, today.month, today.day);
    return dueDay.isAfter(todayDay);
  }

  Member? _assignedMember(BuildContext context) {
    final item = this.item;
    if (item is! ShoppinglistItem || item.assignedToId == null) return null;
    final members =
        context.readOrNull<HouseholdCubit>()?.state.household.member;
    if (members == null) return null;
    for (final m in members) {
      if (m.id == item.assignedToId) return m;
    }
    return null;
  }

  Widget? _annotation(BuildContext context) {
    final item = this.item;
    if (item is! ShoppinglistItem) return null;
    final member = _assignedMember(context);
    if (item.dueDate == null && member == null) return null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (item.dueDate != null)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Text(
                DateFormat.Md().format(item.dueDate!),
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
          if (member != null)
            Tooltip(
              message: AppLocalizations.of(context)!.assignedTo(member.name),
              child: UserCircleAvatar(
                user: member,
                radius: 10,
                textScaler: const TextScaler.linear(0.6),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final annotation = _annotation(context);

    final Widget child = gridStyle
        ? SelectableButtonCard(
            title: item.name,
            selected: selected,
            icon: ItemIcons.get(item),
            description: (item is ItemWithDescription)
                ? (item as ItemWithDescription).description
                : null,
            onPressed: onPressed != null ? () => onPressed!(item) : null,
            onLongPressed:
                onLongPressed != null ? () => onLongPressed!(item) : null,
            extraOption: extraOption,
            annotation: annotation,
          )
        : SelectableButtonListTile(
            title: item.name,
            selected: selected,
            icon: ItemIcons.get(item),
            listStyle: listStyle,
            raised: raised ??
                item is ShoppinglistItem || item is RecipeItem && selected,
            description: (item is ItemWithDescription)
                ? (item as ItemWithDescription).description
                : null,
            onPressed: onPressed != null ? () => onPressed!(item) : null,
            onLongPressed:
                onLongPressed != null ? () => onLongPressed!(item) : null,
            extraOption: extraOption,
            annotation: annotation,
          );

    if (_dueInFuture) {
      return Opacity(opacity: 0.5, child: child);
    }
    return child;
  }
}
