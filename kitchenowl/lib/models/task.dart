import 'package:kitchenowl/models/model.dart';
import 'package:kitchenowl/models/nullable.dart';

class Task extends Model {
  static const rotationNone = 'none';
  static const rotationOrdered = 'ordered';
  static const rotationRandom = 'random';
  static const units = ['day', 'week', 'month'];

  final int? id;
  final String name;
  final bool recurring;
  final DateTime? dueDate;
  final int? repeatEvery;
  final String? repeatUnit;
  final String rotationMode;
  final int? assignedTo;
  final int? createdBy;
  final DateTime? completedAt;
  final List<int> participants;

  const Task({
    this.id,
    this.name = '',
    this.recurring = false,
    this.dueDate,
    this.repeatEvery,
    this.repeatUnit,
    this.rotationMode = rotationNone,
    this.assignedTo,
    this.createdBy,
    this.completedAt,
    this.participants = const [],
  });

  factory Task.fromJson(Map<String, dynamic> map) {
    DateTime? dueDate;
    if (map['due_date'] != null) {
      final utc = DateTime.fromMillisecondsSinceEpoch(
        map['due_date'],
        isUtc: true,
      );
      // due dates are plain dates: keep the calendar day, drop the timezone
      dueDate = DateTime(utc.year, utc.month, utc.day);
    }

    return Task(
      id: map['id'],
      name: map['name'],
      recurring: map['recurring'] ?? false,
      dueDate: dueDate,
      repeatEvery: map['repeat_every'],
      repeatUnit: map['repeat_unit'],
      rotationMode: map['rotation_mode'] ?? rotationNone,
      assignedTo: map['assigned_to'],
      createdBy: map['created_by'],
      completedAt: map['completed_at'] != null
          ? DateTime.fromMillisecondsSinceEpoch(map['completed_at'],
              isUtc: true)
          : null,
      participants: List<int>.from(map['participants'] ?? const []),
    );
  }

  Task copyWith({
    String? name,
    bool? recurring,
    Nullable<DateTime>? dueDate,
    Nullable<int>? repeatEvery,
    Nullable<String>? repeatUnit,
    String? rotationMode,
    Nullable<int>? assignedTo,
    List<int>? participants,
  }) =>
      Task(
        id: id,
        name: name ?? this.name,
        recurring: recurring ?? this.recurring,
        dueDate: (dueDate ?? Nullable(this.dueDate)).value,
        repeatEvery: (repeatEvery ?? Nullable(this.repeatEvery)).value,
        repeatUnit: (repeatUnit ?? Nullable(this.repeatUnit)).value,
        rotationMode: rotationMode ?? this.rotationMode,
        assignedTo: (assignedTo ?? Nullable(this.assignedTo)).value,
        createdBy: createdBy,
        completedAt: completedAt,
        participants: participants ?? this.participants,
      );

  bool get isCompleted => completedAt != null;

  bool get hasRotation => rotationMode != rotationNone;

  bool get isOverdue {
    if (dueDate == null || isCompleted) return false;
    final now = DateTime.now();

    return dueDate!.isBefore(DateTime(now.year, now.month, now.day));
  }

  @override
  List<Object?> get props => [
        id,
        name,
        recurring,
        dueDate,
        repeatEvery,
        repeatUnit,
        rotationMode,
        assignedTo,
        createdBy,
        completedAt,
        participants,
      ];

  @override
  Map<String, dynamic> toJson() => {
        "name": name,
        "recurring": recurring,
        // explicit nulls so that clearing a field reaches the server
        "due_date": dueDate == null
            ? null
            : DateTime.utc(dueDate!.year, dueDate!.month, dueDate!.day)
                .millisecondsSinceEpoch,
        "repeat_every": repeatEvery,
        "repeat_unit": repeatUnit,
        "rotation_mode": rotationMode,
        "assigned_to": assignedTo,
        "participants": participants,
      };

  @override
  Map<String, dynamic> toJsonWithId() => toJson()
    ..addAll({
      "id": id,
    });
}
