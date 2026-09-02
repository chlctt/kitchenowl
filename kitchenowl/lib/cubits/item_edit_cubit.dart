import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/models/category.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/models/recipe.dart';
import 'package:kitchenowl/models/shoppinglist.dart';
import 'package:kitchenowl/services/api/api_service.dart';
import 'package:kitchenowl/services/transaction_handler.dart';
import 'package:kitchenowl/services/transactions/item.dart';
import 'package:kitchenowl/services/transactions/shoppinglist.dart';

class ItemEditCubit<T extends Item> extends Cubit<ItemEditState> {
  final Household? household;
  final T _item;
  final ShoppingList? shoppingList;

  T get item {
    if (_item is ItemWithDescription) {
      return (((_item as ItemWithDescription).copyWith(
        description: state.description,
        category: Nullable(state.category),
        icon: Nullable(state.icon),
        name: state.name,
      )) as T);
    }

    return _item.copyWith(
      category: Nullable(state.category),
      icon: Nullable(state.icon),
      name: state.name,
    ) as T;
  }

  ItemEditCubit({required T item, required this.household, this.shoppingList})
      : _item = item,
        super(ItemEditState(
          description: (item is ItemWithDescription) ? item.description : '',
          icon: item.icon,
          name: item.name,
          category: item.category,
          assignedToId: (item is ShoppinglistItem) ? item.assignedToId : null,
          dueDate: (item is ShoppinglistItem) ? item.dueDate : null,
        )) {
    refresh();
  }

  Future<void> refresh() async {
    if (_item.id != null) {
      final recipes = (await TransactionHandler.getInstance()
          .runTransaction(TransactionItemGetRecipes(
        household: household,
        item: _item,
      )))
        ..sort(((a, b) {
          if (a.isPlanned == b.isPlanned) {
            return 0;
          } else if (b.isPlanned) {
            return 1;
          } else {
            return -1;
          }
        }));
      emit(state.copyWith(recipes: recipes));
    }
  }

  Future<void> saveItem() async {
    final assigneeChanged = state.hasChangedAssignee(_item);
    final dueDateChanged = state.hasChangedDueDate(_item);
    if (shoppingList != null &&
        (state.hasChangedDescription(_item) ||
            assigneeChanged ||
            dueDateChanged)) {
      await TransactionHandler.getInstance()
          .runTransaction(TransactionShoppingListUpdateItem(
        household: household!,
        shoppinglist: shoppingList!,
        item: _item,
        description: state.description,
        assignedTo: assigneeChanged ? Nullable(state.assignedToId) : null,
        dueDate: dueDateChanged ? Nullable(state.dueDate) : null,
      ));
    }
    if (state.hasChangedItem(_item)) {
      if (item.id != null) {
        await TransactionHandler.getInstance()
            .runTransaction(TransactionItemUpdate(
          item: item,
        ));
      } else if (household != null) {
        await TransactionHandler.getInstance()
            .runTransaction(TransactionItemAdd(
          household: household!,
          item: item,
        ));
      }
    }
  }

  Future<bool> deleteItem() async {
    if (_item.id != null) {
      return ApiService.getInstance().deleteItem(_item);
    }

    return false;
  }

  Future<bool> mergeItem(Item other) async {
    if (_item.id != null &&
        other.id != null &&
        await ApiService.getInstance().mergeItems(_item, other)) {
      emit(state.copyWith(hasMerged: true));
      return true;
    }

    return false;
  }

  void setName(String name) {
    emit(state.copyWith(name: name));
  }

  void setDescription(String desc) {
    emit(state.copyWith(description: desc));
  }

  void setCategory(Category? category) {
    emit(state.copyWith(
      category: Nullable(category),
    ));
  }

  void setIcon(String? icon) {
    emit(state.copyWith(
      icon: Nullable(icon),
    ));
  }

  void setAssignedTo(int? userId) {
    emit(state.copyWith(assignedToId: Nullable(userId)));
  }

  void setDueDate(DateTime? date) {
    emit(state.copyWith(dueDate: Nullable(date)));
  }
}

class ItemEditState extends Equatable {
  final String name;
  final String description;
  final String? icon;
  final List<Recipe> recipes;
  final Category? category;
  final bool hasMerged;
  final int? assignedToId;
  final DateTime? dueDate;

  const ItemEditState({
    this.name = "",
    this.description = "",
    this.icon,
    this.recipes = const [],
    this.category,
    this.hasMerged = false,
    this.assignedToId,
    this.dueDate,
  });

  ItemEditState copyWith({
    String? name,
    String? description,
    Nullable<String>? icon,
    List<Recipe>? recipes,
    Nullable<Category>? category,
    bool? hasMerged,
    Nullable<int>? assignedToId,
    Nullable<DateTime>? dueDate,
  }) =>
      ItemEditState(
        name: name ?? this.name,
        description: description ?? this.description,
        icon: (icon ?? Nullable(this.icon)).value,
        recipes: recipes ?? this.recipes,
        category: (category ?? Nullable(this.category)).value,
        hasMerged: hasMerged ?? this.hasMerged,
        assignedToId: (assignedToId ?? Nullable(this.assignedToId)).value,
        dueDate: (dueDate ?? Nullable(this.dueDate)).value,
      );

  @override
  List<Object?> get props =>
      [name, description, icon, recipes, category, hasMerged, assignedToId, dueDate];

  bool hasChanged(Item comparedTo) =>
      hasChangedItem(comparedTo) ||
      hasChangedDescription(comparedTo) ||
      hasChangedAssignee(comparedTo) ||
      hasChangedDueDate(comparedTo);

  bool hasChangedItem(Item comparedTo) =>
      comparedTo.category != category ||
      comparedTo.icon != icon ||
      comparedTo.name != name ||
      hasMerged;

  bool hasChangedDescription(Item comparedTo) {
    return comparedTo is ItemWithDescription &&
        (comparedTo).description != description;
  }

  bool hasChangedAssignee(Item comparedTo) =>
      comparedTo is ShoppinglistItem &&
      comparedTo.assignedToId != assignedToId;

  bool hasChangedDueDate(Item comparedTo) =>
      comparedTo is ShoppinglistItem && comparedTo.dueDate != dueDate;
}
