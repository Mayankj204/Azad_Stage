/// Question types supported by the survey form.
enum QuestionType {
  textInput,
  numberInput,
  singleSelect,
  multiSelect,
  dropdown,
  date,
  yesNo,
  autoCalculated,
}

/// Section identifiers for the survey.
enum SectionId {
  main,
  womenDetails,
  // V2 Family Survey sections
  basicInfo,
  menBoysCount,
  menBoysDetails,
  womenGirlsCount,
  womenGirlsDetails,
  eligibleWoman,          // kept for backward compat
  eligibleWomenCount,     // NEW: how many eligible women
  eligibleWomenDetails,   // NEW: repeating group per eligible woman
  drivingInterest,
  documents,
  remarks,
}

/// An option for dropdown, single-select, multi-select, or yesNo questions.
class QuestionOption {
  final dynamic value;
  final String en;
  final String hi;
  final String bn;
  final String ta;

  const QuestionOption({
    required this.value,
    required this.en,
    this.hi = '',
    this.bn = '',
    this.ta = '',
  });

  String label(String locale) {
    switch (locale) {
      case 'hi':
        return hi.isNotEmpty ? hi : en;
      case 'bn':
        return bn.isNotEmpty ? bn : en;
      case 'ta':
        return ta.isNotEmpty ? ta : en;
      default:
        return en;
    }
  }
}

/// Definition of a single question in the survey form.
class QuestionDefinition {
  final String id;
  final String fieldName;
  final SectionId section;
  final QuestionType type;
  final String en;
  final String hi;
  final String bn;
  final String ta;
  final List<QuestionOption>? options;
  final bool required;
  final String? conditionalOnField;
  final dynamic conditionalValue;
  final List<dynamic>? conditionalValues;
  final QKeyboardType? keyboardType;
  final int? maxDigits;
  final int? minValue;
  final int? maxValue;
  final int? exactLength;
  final List<String>? formulaFields;
  final String? dependsOnField;
  final bool autoFilled;
  final int? number;

  const QuestionDefinition({
    required this.id,
    required this.fieldName,
    required this.section,
    required this.type,
    required this.en,
    this.hi = '',
    this.bn = '',
    this.ta = '',
    this.options,
    this.required = false,
    this.conditionalOnField,
    this.conditionalValue,
    this.conditionalValues,
    this.keyboardType,
    this.maxDigits,
    this.minValue,
    this.maxValue,
    this.exactLength,
    this.formulaFields,
    this.dependsOnField,
    this.autoFilled = false,
    this.number,
  });

  String questionText(String locale) {
    switch (locale) {
      case 'hi':
        return hi.isNotEmpty ? hi : en;
      case 'bn':
        return bn.isNotEmpty ? bn : en;
      case 'ta':
        return ta.isNotEmpty ? ta : en;
      default:
        return en;
    }
  }

  /// Standard Yes/No options with option codes (1 = Yes, 2 = No).
  static const List<QuestionOption> yesNoOptions = [
    QuestionOption(value: 1, en: 'Yes', hi: 'हाँ', bn: 'হ্যাঁ', ta: 'ஆம்'),
    QuestionOption(value: 2, en: 'No', hi: 'नहीं', bn: 'না', ta: 'இல்லை'),
  ];
}

/// Keyboard type constants for question definitions.
class QKeyboardType {
  final String name;
  const QKeyboardType._(this.name);
  static const text = QKeyboardType._('text');
  static const number = QKeyboardType._('number');
  static const phone = QKeyboardType._('phone');
  static const multiline = QKeyboardType._('multiline');
}
