import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/question.dart';
import '../../providers/assessment_provider.dart';
import '../../providers/locale_provider.dart';
import '../../widgets/question_widgets/single_select_widget.dart';
import '../../widgets/question_widgets/multi_select_widget.dart';
import '../../widgets/question_widgets/text_input_widget.dart';
import '../../widgets/question_widgets/number_input_widget.dart';
import '../../widgets/question_widgets/dropdown_widget.dart';
import '../../widgets/question_widgets/yes_no_widget.dart';
import '../../widgets/question_widgets/date_picker_widget.dart';
import '../../widgets/progress_indicator.dart' as custom;

class QuestionScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<SurveyProvider>(context);
    final locale = Provider.of<LocaleProvider>(context);
    final lang = locale.languageCode;
    final question = provider.currentQuestion;
    final isReadOnly = provider.isReadOnly;
    final isSingleEdit = provider.editingSingleQuestion;

    if (question == null) return Scaffold(body: Center(child: Text('No question')));

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        if (isReadOnly || isSingleEdit) {
          Navigator.pop(context);
        } else {
          _showExitDialog(context, lang);
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(isReadOnly
              ? _t(lang, 'சர்வே பார்க்க', 'সমীক্ষা দেখুন', 'सर्वेक्षण देखें', 'View Survey')
              : isSingleEdit
                  ? _t(lang, 'கேள்வியை திருத்து', 'প্রশ্ন সম্পাদনা', 'प्रश्न संपादित करें', 'Edit Question')
                  : provider.getSectionTitle(lang)),
          leading: IconButton(
            icon: Icon(isReadOnly || isSingleEdit ? Icons.arrow_back : Icons.close),
            onPressed: () {
              if (isReadOnly || isSingleEdit) {
                Navigator.pop(context);
              } else {
                _showExitDialog(context, lang);
              }
            },
          ),
        ),
        body: Column(
          children: [
            // Progress bar (hide in single-edit mode)
            if (!isSingleEdit)
              custom.AssessmentProgressIndicator(
                progress: provider.progress,
                current: provider.currentIndex + 1,
                total: provider.totalQuestions,
                sectionTitle: provider.getSectionTitle(lang),
              ),

            // Question content (no GestureDetector — it was stealing taps from child widgets)
            Expanded(
              child: SingleChildScrollView(
                padding: EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Question text with number prefix
                    RichText(
                      text: TextSpan(
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, height: 1.4, color: Colors.black87),
                        children: [
                          if (question.number != null)
                            TextSpan(text: '${question.number}. '),
                          TextSpan(text: question.questionText(lang)),
                          if (question.required && !isReadOnly)
                            TextSpan(text: ' *', style: TextStyle(color: Colors.red)),
                        ],
                      ),
                    ),
                    SizedBox(height: 24),

                    // Question widget based on type
                    _buildQuestionWidget(question, provider, lang, isReadOnly),
                  ],
                ),
              ),
            ),

            // Navigation buttons — extra bottom padding to avoid system nav bar
            Container(
              padding: EdgeInsets.fromLTRB(16, 12, 16, 32),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, -2))],
              ),
              child: SafeArea(
                top: false,
                child: isSingleEdit
                  ? Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            icon: Icon(Icons.check),
                            label: Text(_t(lang, 'சேமித்து திரும்பு', 'সংরক্ষণ করুন', 'सहेजें और वापस', 'Save & Back')),
                            onPressed: () {
                              provider.clearEditingSingleQuestion();
                              Navigator.pop(context);
                            },
                          ),
                        ),
                      ],
                    )
                  : Row(
                      children: [
                        if (!provider.isFirstQuestion)
                          Expanded(
                            child: OutlinedButton.icon(
                              icon: Icon(Icons.arrow_back),
                              label: Text(_t(lang, 'பின்', 'পিছনে', 'पीछे', 'Back')),
                              onPressed: () => provider.previous(),
                            ),
                          ),
                        if (!provider.isFirstQuestion) SizedBox(width: 12),
                        Expanded(
                          flex: 2,
                          child: ElevatedButton.icon(
                            icon: Icon(_getNextIcon(provider, isReadOnly)),
                            label: Text(_getNextLabel(provider, lang, isReadOnly)),
                            onPressed: () => _handleNext(context, provider, isReadOnly),
                          ),
                        ),
                      ],
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Translation helper — returns the correct string based on locale
  String _t(String lang, String ta, String bn, String hi, String en) {
    switch (lang) {
      case 'ta': return ta;
      case 'bn': return bn;
      case 'hi': return hi;
      default: return en;
    }
  }

  IconData _getNextIcon(SurveyProvider provider, bool isReadOnly) {
    if (provider.isLastQuestion) {
      return isReadOnly ? Icons.done : Icons.check;
    }
    return Icons.arrow_forward;
  }

  String _getNextLabel(SurveyProvider provider, String lang, bool isReadOnly) {
    if (provider.isLastQuestion) {
      if (isReadOnly) {
        return _t(lang, 'மூடு', 'বন্ধ করুন', 'बंद करें', 'Close');
      }
      return _t(lang, 'மதிப்பாய்வு', 'পর্যালোচনা', 'समीक्षा करें', 'Review');
    }
    return _t(lang, 'அடுத்து', 'পরবর্তী', 'आगे', 'Next');
  }

  void _handleNext(BuildContext context, SurveyProvider provider, bool isReadOnly) {
    if (provider.isLastQuestion) {
      if (isReadOnly) {
        Navigator.pop(context);
      } else {
        Navigator.pushNamed(context, '/review');
      }
    } else {
      provider.next();
    }
  }

  Widget _buildQuestionWidget(QuestionDefinition q, SurveyProvider provider, String lang, bool isReadOnly) {
    // Get value from the correct model based on current phase
    dynamic currentValue;
    if (provider.phase == SurveyPhase.menBoysDetails && provider.current != null) {
      final idx = provider.currentMenBoyIndex;
      if (idx < provider.current!.menBoys.length) {
        currentValue = provider.current!.menBoys[idx].getField(q.fieldName);
      }
    } else if (provider.phase == SurveyPhase.womenGirlsDetails && provider.current != null) {
      final idx = provider.currentWomanGirlIndex;
      if (idx < provider.current!.womenGirls.length) {
        currentValue = provider.current!.womenGirls[idx].getField(q.fieldName);
      }
    } else if (provider.phase == SurveyPhase.eligibleWomenDetails && provider.current != null) {
      final idx = provider.currentEligibleWomanIndex;
      if (idx < provider.current!.eligibleWomen.length) {
        currentValue = provider.current!.eligibleWomen[idx].getField(q.fieldName);
      }
    } else {
      currentValue = provider.current?.getField(q.fieldName);
    }

    // In read-only mode, show a display-only view of the value
    if (isReadOnly) {
      return _buildReadOnlyDisplay(q, currentValue, lang);
    }

    // Use a unique key per question + member to force fresh widget state
    final keyStr = provider.phase == SurveyPhase.menBoysDetails
        ? '${q.fieldName}_mb${provider.currentMenBoyIndex}'
        : provider.phase == SurveyPhase.womenGirlsDetails
            ? '${q.fieldName}_wg${provider.currentWomanGirlIndex}'
            : provider.phase == SurveyPhase.eligibleWomenDetails
                ? '${q.fieldName}_ew${provider.currentEligibleWomanIndex}'
                : q.fieldName;

    switch (q.type) {
      case QuestionType.yesNo:
        return YesNoWidget(
          key: ValueKey(keyStr),
          value: currentValue as int?,
          locale: lang,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.dropdown:
        return DropdownWidget(
          key: ValueKey(keyStr),
          options: q.options ?? [],
          value: currentValue?.toString(),
          locale: lang,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.textInput:
        return TextInputWidget(
          key: ValueKey(keyStr),
          value: currentValue?.toString() ?? '',
          multiline: q.keyboardType == QKeyboardType.multiline,
          isPhone: q.keyboardType == QKeyboardType.phone,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.numberInput:
        return NumberInputWidget(
          key: ValueKey(keyStr),
          value: currentValue,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.singleSelect:
        return SingleSelectWidget(
          key: ValueKey(keyStr),
          options: q.options ?? [],
          value: currentValue,
          locale: lang,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.multiSelect:
        return MultiSelectWidget(
          key: ValueKey(keyStr),
          options: q.options ?? [],
          values: currentValue as List<String>? ?? [],
          locale: lang,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.date:
        return DatePickerWidget(
          key: ValueKey(keyStr),
          value: currentValue as String?,
          locale: lang,
          onChanged: (val) => provider.answerCurrent(val),
        );
      case QuestionType.autoCalculated:
        final displayValue = currentValue != null
            ? currentValue.toStringAsFixed(2)
            : _t(lang, 'தானாக கணக்கிடப்படும்', 'স্বয়ংক্রিয়ভাবে গণনা হবে', 'स्वतः गणना होगी', 'Auto-calculated');
        return Container(
          key: ValueKey(keyStr),
          padding: EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Row(
            children: [
              Icon(Icons.calculate, color: Colors.grey),
              SizedBox(width: 12),
              Text(displayValue, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            ],
          ),
        );
    }
  }

  Widget _buildReadOnlyDisplay(QuestionDefinition q, dynamic value, String lang) {
    String displayValue;
    if (value == null || (value is String && value.isEmpty)) {
      displayValue = _t(lang, 'பதிலளிக்கவில்லை', 'উত্তর দেওয়া হয়নি', 'उत्तर नहीं दिया', 'Not answered');
    } else if (value is List) {
      if (q.options != null) {
        displayValue = value.map((v) {
          final opt = q.options!.where((o) => o.value.toString() == v.toString()).toList();
          return opt.isNotEmpty ? opt.first.label(lang) : v.toString();
        }).join(', ');
      } else {
        displayValue = value.join(', ');
      }
    } else if (q.type == QuestionType.yesNo) {
      displayValue = value == 1
          ? _t(lang, 'ஆம்', 'হ্যাঁ', 'हाँ', 'Yes')
          : _t(lang, 'இல்லை', 'না', 'नहीं', 'No');
    } else if (q.options != null) {
      final opt = q.options!.where((o) => o.value.toString() == value.toString()).toList();
      displayValue = opt.isNotEmpty ? opt.first.label(lang) : value.toString();
    } else if (value is double) {
      displayValue = value.toStringAsFixed(2);
    } else {
      displayValue = value.toString();
    }

    final hasValue = value != null && (value is! String || value.isNotEmpty);

    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Text(
        displayValue,
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w500,
          color: hasValue ? Colors.black87 : Colors.grey,
        ),
      ),
    );
  }

  void _showExitDialog(BuildContext context, String lang) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(_t(lang, 'கணக்கெடுப்பை விட்டு வெளியேறவா?', 'সমীক্ষা ত্যাগ করবেন?', 'सर्वेक्षण छोड़ें?', 'Exit Survey?')),
        content: Text(_t(lang, 'உங்கள் முன்னேற்றம் வரைவாக சேமிக்கப்படும்.', 'আপনার অগ্রগতি খসড়া হিসাবে সংরক্ষিত হবে।', 'आपकी प्रगति ड्राफ्ट के रूप में सहेजी जाएगी।', 'Your progress will be saved as a draft.')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text(_t(lang, 'ரத்துசெய்', 'বাতিল', 'रद्द करें', 'Cancel'))),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              Navigator.popUntil(context, (route) => route.settings.name == '/home' || route.isFirst);
            },
            child: Text(_t(lang, 'வெளியேறு', 'বাহির', 'बाहर निकलें', 'Exit'), style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
