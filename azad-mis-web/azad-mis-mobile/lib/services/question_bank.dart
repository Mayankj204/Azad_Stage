import '../models/question.dart';

/// V2 Family Survey Form question definitions.
/// Phases: basicInfo → menBoysCount → menBoysDetails → womenGirlsCount →
///         womenGirlsDetails → eligibleWomenCount → eligibleWomenDetails →
///         drivingInterest → documents → remarks
class QuestionBank {
  // =========================================================================
  // PHASE 1: BASIC INFO (Q1-Q33) — flat scrollable form
  // =========================================================================
  static const List<QuestionDefinition> basicInfoQuestions = [
    // Q1: State
    QuestionDefinition(
      id: 'state',
      fieldName: 'state',
      number: 1,
      section: SectionId.basicInfo,
      type: QuestionType.dropdown,
      required: true,
      autoFilled: true,
      en: 'State',
      hi: 'राज्य',
      bn: 'রাজ্য',
      ta: 'மாநிலம்',
      options: [
        QuestionOption(value: 'Delhi', en: 'Delhi', hi: 'दिल्ली', bn: 'দিল্লি', ta: 'டெல்லி'),
        QuestionOption(value: 'Rajasthan', en: 'Rajasthan', hi: 'राजस्थान', bn: 'রাজস্থান', ta: 'ராஜஸ்தான்'),
        QuestionOption(value: 'West Bengal', en: 'West Bengal', hi: 'पश्चिम बंगाल', bn: 'পশ্চিমবঙ্গ', ta: 'மேற்கு வங்காளம்'),
      ],
    ),

    // Q2: Name of surveyer
    QuestionDefinition(
      id: 'surveyer',
      fieldName: 'surveyer',
      number: 2,
      section: SectionId.basicInfo,
      type: QuestionType.dropdown,
      required: true,
      autoFilled: true,
      en: 'Name of surveyer',
      hi: 'सर्वेक्षक का नाम',
      bn: 'সমীক্ষকের নাম',
      ta: 'கணக்கெடுப்பாளர் பெயர்',
      dependsOnField: 'state',
      options: [],
    ),

    // Q3: Designation
    QuestionDefinition(
      id: 'designation',
      fieldName: 'designation',
      number: 3,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      autoFilled: true,
      en: 'Designation',
      hi: 'पदनाम',
      bn: 'পদবি',
      ta: 'பதவி',
    ),

    // Q4: Date of Survey
    QuestionDefinition(
      id: 'dt_survey',
      fieldName: 'dtSurvey',
      number: 4,
      section: SectionId.basicInfo,
      type: QuestionType.date,
      required: true,
      autoFilled: true,
      en: 'Date of Survey',
      hi: 'सर्वेक्षण की तारीख',
      bn: 'সমীক্ষার তারিখ',
      ta: 'கணக்கெடுப்பு தேதி',
    ),

    // Q5: Quarter of Survey
    QuestionDefinition(
      id: 'qtr_survey',
      fieldName: 'qtrSurvey',
      number: 5,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      autoFilled: true,
      en: 'Quarter of Survey',
      hi: 'सर्वेक्षण का तिमाही',
      bn: 'সমীক্ষার ত্রৈমাসিক',
      ta: 'கணக்கெடுப்பு காலாண்டு',
      options: [
        QuestionOption(value: 'Q1', en: 'Q1 (Apr-Jun)', hi: 'तिमाही 1 (अप्रैल-जून)', bn: 'ত্রৈমাসিক ১ (এপ্রিল-জুন)', ta: 'காலாண்டு 1 (ஏப்-ஜூன்)'),
        QuestionOption(value: 'Q2', en: 'Q2 (Jul-Sep)', hi: 'तिमाही 2 (जुलाई-सितम्बर)', bn: 'ত্রৈমাসিক ২ (জুলাই-সেপ্টেম্বর)', ta: 'காலாண்டு 2 (ஜூலை-செப்)'),
        QuestionOption(value: 'Q3', en: 'Q3 (Oct-Dec)', hi: 'तिमाही 3 (अक्टूबर-दिसम्बर)', bn: 'ত্রৈমাসিক ৩ (অক্টোবর-ডিসেম্বর)', ta: 'காலாண்டு 3 (அக்-டிச)'),
        QuestionOption(value: 'Q4', en: 'Q4 (Jan-Mar)', hi: 'तिमाही 4 (जनवरी-मार्च)', bn: 'ত্রৈমাসিক ৪ (জানুয়ারি-মার্চ)', ta: 'காலாண்டு 4 (ஜன-மார்)'),
      ],
    ),

    // Q6: Name of Basti
    QuestionDefinition(
      id: 'name_basti',
      fieldName: 'nameBasti',
      number: 6,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: 'Name of Basti',
      hi: 'बस्ती का नाम',
      bn: 'বস্তির নাম',
      ta: 'குடியிருப்பின் பெயர்',
    ),

    // Q7: District
    QuestionDefinition(
      id: 'district',
      fieldName: 'district',
      number: 7,
      section: SectionId.basicInfo,
      type: QuestionType.dropdown,
      required: true,
      en: 'District',
      hi: 'जिला',
      bn: 'জেলা',
      ta: 'மாவட்டம்',
      dependsOnField: 'state',
      options: [],
    ),

    // Q8: Centre census
    QuestionDefinition(
      id: 'center',
      fieldName: 'center',
      number: 8,
      section: SectionId.basicInfo,
      type: QuestionType.dropdown,
      required: true,
      autoFilled: true,
      en: 'Centre census',
      hi: 'सेंटर जनगणना',
      bn: 'কেন্দ্র শুমারি',
      ta: 'மைய மக்கள்தொகை கணக்கெடுப்பு',
      dependsOnField: 'district',
      options: [],
    ),

    // Q9: Name of Area census
    QuestionDefinition(
      id: 'area_name',
      fieldName: 'areaName',
      number: 9,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      en: 'Name of Area census',
      hi: 'क्षेत्र जनगणना का नाम',
      bn: 'এলাকা শুমারির নাম',
      ta: 'பகுதி மக்கள்தொகை கணக்கெடுப்பு பெயர்',
      dependsOnField: 'center',
      options: [],
    ),

    // Q10: Specify, If any other
    QuestionDefinition(
      id: 'area_other',
      fieldName: 'areaOther',
      number: 10,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      en: 'Specify, If any other',
      hi: 'यदि कोई अन्य हो तो बताएं',
      bn: 'অন্য কিছু হলে উল্লেখ করুন',
      ta: 'வேறு ஏதேனும் இருந்தால் குறிப்பிடவும்',
    ),

    // Q11: Name with whom the survey is done
    QuestionDefinition(
      id: 'head_name',
      fieldName: 'headName',
      number: 11,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: 'Name with whom the survey is done',
      hi: 'जिनके साथ सर्वेक्षण किया गया है उनका नाम',
      bn: 'যার সাথে সমীক্ষা করা হয়েছে তার নাম',
      ta: 'கணக்கெடுப்பு யாருடன் செய்யப்பட்டது',
    ),

    // Q12: Address
    QuestionDefinition(
      id: 'head_address',
      fieldName: 'headAddress',
      number: 12,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: 'Address',
      hi: 'पता',
      bn: 'ঠিকানা',
      ta: 'முகவரி',
      keyboardType: QKeyboardType.multiline,
    ),

    // Q13: Contact Number
    QuestionDefinition(
      id: 'head_phone',
      fieldName: 'headPhone',
      number: 13,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: 'Contact Number',
      hi: 'संपर्क नंबर',
      bn: 'যোগাযোগ নম্বর',
      ta: 'தொடர்பு எண்',
      keyboardType: QKeyboardType.phone,
      maxDigits: 10,
      exactLength: 10,
    ),

    // Q14: Caste Category
    QuestionDefinition(
      id: 'caste_category',
      fieldName: 'casteCategory',
      number: 14,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      en: 'Caste Category',
      hi: 'जाति श्रेणी',
      bn: 'জাতি বিভাগ',
      ta: 'சாதி வகை',
      options: [
        QuestionOption(value: 'SC', en: 'SC (Scheduled Caste)', hi: 'अनुसूचित जाति', bn: 'তফসিলি জাতি', ta: 'பட்டியல் சாதி'),
        QuestionOption(value: 'ST', en: 'ST (Scheduled Tribe)', hi: 'अनुसूचित जनजाति', bn: 'তফসিলি উপজাতি', ta: 'பட்டியல் பழங்குடி'),
        QuestionOption(value: 'OBC', en: 'OBC (Other Backward Class)', hi: 'अन्य पिछड़ा वर्ग', bn: 'অন্যান্য অনগ্রসর শ্রেণী', ta: 'பிற பிற்படுத்தப்பட்ட வகுப்பு'),
        QuestionOption(value: 'General', en: 'General', hi: 'सामान्य', bn: 'সাধারণ', ta: 'பொது'),
      ],
    ),

    // Q15: Caste sub-category or detail (hidden/conditional)
    QuestionDefinition(
      id: 'caste_detail',
      fieldName: 'casteDetail',
      number: 15,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      en: 'Caste (Specify)',
      hi: 'जाति (निर्दिष्ट करें)',
      bn: 'জাতি (নির্দিষ্ট করুন)',
      ta: 'சாதி (குறிப்பிடவும்)',
    ),

    // Q16: Religion
    QuestionDefinition(
      id: 'religion',
      fieldName: 'religion',
      number: 16,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      en: 'Religion',
      hi: 'धर्म',
      bn: 'ধর্ম',
      ta: 'மதம்',
      options: [
        QuestionOption(value: 'Hindu', en: 'Hindu', hi: 'हिन्दू', bn: 'হিন্দু', ta: 'இந்து'),
        QuestionOption(value: 'Muslim', en: 'Muslim', hi: 'मुस्लिम', bn: 'মুসলিম', ta: 'முஸ்லிம்'),
        QuestionOption(value: 'Christian', en: 'Christian', hi: 'ईसाई', bn: 'খ্রিস্টান', ta: 'கிறிஸ்தவர்'),
        QuestionOption(value: 'Sikh', en: 'Sikh', hi: 'सिख', bn: 'শিখ', ta: 'சீக்கியர்'),
        QuestionOption(value: 'Buddhist', en: 'Buddhist', hi: 'बौद्ध', bn: 'বৌদ্ধ', ta: 'புத்தர்'),
        QuestionOption(value: 'Other', en: 'Other', hi: 'अन्य', bn: 'অন্যান্য', ta: 'மற்றவை'),
      ],
    ),

    // Q17: Religion specify other (hidden/conditional)
    QuestionDefinition(
      id: 'religion_other',
      fieldName: 'religionOther',
      number: 17,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      en: 'Specify Religion (if Other)',
      hi: 'धर्म बताएं (यदि अन्य)',
      bn: 'ধর্ম উল্লেখ করুন (যদি অন্য)',
      ta: 'மதம் குறிப்பிடவும் (மற்றவை எனில்)',
      conditionalOnField: 'religion',
      conditionalValue: 'Other',
    ),

    // Q18: Total Family members
    QuestionDefinition(
      id: 'total_family_members',
      fieldName: 'totalFamilyMembers',
      number: 18,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: true,
      en: 'Total Family members',
      hi: 'परिवार के कुल सदस्य',
      bn: 'মোট পরিবারের সদস্য',
      ta: 'மொத்த குடும்ப உறுப்பினர்கள்',
      maxDigits: 2,
      maxValue: 30,
    ),

    // Q19: How many earning members
    QuestionDefinition(
      id: 'earning_members',
      fieldName: 'earningMembers',
      number: 19,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: true,
      en: 'How many earning members are there in the family',
      hi: 'परिवार में कितने कमाने वाले सदस्य हैं',
      bn: 'পরিবারে কতজন উপার্জনকারী সদস্য আছে',
      ta: 'குடும்பத்தில் எத்தனை சம்பாதிக்கும் உறுப்பினர்கள்',
      maxDigits: 2,
      maxValue: 20,
    ),

    // Q20: Total Monthly Income
    QuestionDefinition(
      id: 'total_monthly_income',
      fieldName: 'totalMonthlyIncome',
      number: 20,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: true,
      en: 'Total Monthly Income',
      hi: 'कुल मासिक आय',
      bn: 'মোট মাসিক আয়',
      ta: 'மொத்த மாத வருமானம்',
      maxDigits: 7,
      maxValue: 9999999,
    ),

    // Q21: Per Capita Income (auto-calculated)
    QuestionDefinition(
      id: 'per_capita_income',
      fieldName: 'perCapitaIncome',
      number: 21,
      section: SectionId.basicInfo,
      type: QuestionType.autoCalculated,
      required: false,
      autoFilled: true,
      en: 'Per Capita Income',
      hi: 'प्रति व्यक्ति आय',
      bn: 'মাথাপিছু আয়',
      ta: 'தனிநபர் வருமானம்',
    ),

    // Q22: Primary decision maker in the family
    QuestionDefinition(
      id: 'primary_decision_maker',
      fieldName: 'primaryDecisionMaker',
      number: 22,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      en: 'Who is the primary decision maker in the family',
      hi: 'परिवार में मुख्य निर्णय लेने वाला कौन है',
      bn: 'পরিবারে প্রধান সিদ্ধান্ত গ্রহণকারী কে',
      ta: 'குடும்பத்தில் முதன்மை முடிவெடுப்பவர் யார்',
      options: [
        QuestionOption(value: 'Father', en: 'Father', hi: 'पिता', bn: 'পিতা', ta: 'தந்தை'),
        QuestionOption(value: 'Mother', en: 'Mother', hi: 'माता', bn: 'মাতা', ta: 'தாய்'),
        QuestionOption(value: 'Husband', en: 'Husband', hi: 'पति', bn: 'স্বামী', ta: 'கணவர்'),
        QuestionOption(value: 'Self', en: 'Self', hi: 'स्वयं', bn: 'নিজে', ta: 'சுயமாக'),
        QuestionOption(value: 'Other', en: 'Other', hi: 'अन्य', bn: 'অন্যান্য', ta: 'மற்றவை'),
      ],
    ),

    // Q23: Decision maker specify (conditional)
    QuestionDefinition(
      id: 'decision_maker_other',
      fieldName: 'decisionMakerOther',
      number: 23,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      en: 'Specify (if Other)',
      hi: 'बताएं (यदि अन्य)',
      bn: 'উল্লেখ করুন (যদি অন্য)',
      ta: 'குறிப்பிடவும் (மற்றவை எனில்)',
      conditionalOnField: 'primaryDecisionMaker',
      conditionalValue: 'Other',
    ),

    // Q24: Education of decision maker (conditional/hidden)
    QuestionDefinition(
      id: 'decision_maker_education',
      fieldName: 'decisionMakerEducation',
      number: 24,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: false,
      en: 'Education of primary decision maker',
      hi: 'मुख्य निर्णयकर्ता की शिक्षा',
      bn: 'প্রধান সিদ্ধান্ত গ্রহণকারীর শিক্ষা',
      ta: 'முதன்மை முடிவெடுப்பவரின் கல்வி',
    ),

    // Q25: Occupation of primary decision maker
    QuestionDefinition(
      id: 'decision_maker_occupation',
      fieldName: 'decisionMakerOccupation',
      number: 25,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: 'What is the occupation of primary decision maker of the family',
      hi: 'परिवार के मुख्य निर्णयकर्ता का व्यवसाय क्या है',
      bn: 'পরিবারের প্রধান সিদ্ধান্ত গ্রহণকারীর পেশা কী',
      ta: 'குடும்பத்தின் முதன்மை முடிவெடுப்பவரின் தொழில் என்ன',
    ),

    // Q26: Family's Native Place
    QuestionDefinition(
      id: 'family_native_place',
      fieldName: 'familyNativePlace',
      number: 26,
      section: SectionId.basicInfo,
      type: QuestionType.textInput,
      required: true,
      en: "Family's Native Place",
      hi: 'परिवार का मूल स्थान',
      bn: 'পরিবারের আদি নিবাস',
      ta: 'குடும்பத்தின் சொந்த ஊர்',
    ),

    // Q27: Total male members in the family
    QuestionDefinition(
      id: 'total_male_members',
      fieldName: 'totalMaleMembers',
      number: 27,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: true,
      en: 'Total male members in the family',
      hi: 'परिवार में कुल पुरुष सदस्य',
      bn: 'পরিবারে মোট পুরুষ সদস্য',
      ta: 'குடும்பத்தில் மொத்த ஆண் உறுப்பினர்கள்',
      maxDigits: 2,
      maxValue: 20,
    ),

    // Q28: If there is a boy 13-18, will you prefer him joining MGJ in Azad
    QuestionDefinition(
      id: 'boy_13_18_mgj',
      fieldName: 'boy1318Mgj',
      number: 28,
      section: SectionId.basicInfo,
      type: QuestionType.yesNo,
      required: true,
      en: 'If there is a boy in the age group of 13-18 in the house, will you prefer him joining MGJ in Azad',
      hi: 'अगर घर में 13-18 आयु वर्ग का कोई लड़का है, तो क्या आप चाहेंगे कि वह आज़ाद में MGJ में शामिल हो',
      bn: 'ঘরে যদি ১৩-১৮ বছর বয়সী ছেলে থাকে, তাহলে কি আপনি চান তাকে আজাদ MGJ-তে যোগ দিতে',
      ta: 'வீட்டில் 13-18 வயதுக்குட்பட்ட சிறுவன் இருந்தால், அவர் ஆஸாத் MGJ-ல் சேர விரும்புவீர்களா',
    ),

    // Q29: How many boys 13-18 (conditional/hidden)
    QuestionDefinition(
      id: 'boys_13_18_count',
      fieldName: 'boys1318Count',
      number: 29,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: false,
      en: 'How many boys aged 13-18',
      hi: '13-18 आयु के कितने लड़के',
      bn: '১৩-১৮ বছরের কতজন ছেলে',
      ta: '13-18 வயது சிறுவர்கள் எத்தனை',
      maxDigits: 1,
      maxValue: 9,
      conditionalOnField: 'boy1318Mgj',
      conditionalValue: '1',
    ),

    // Q30: Total Female members in the family
    QuestionDefinition(
      id: 'total_female_members',
      fieldName: 'totalFemaleMembers',
      number: 30,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: true,
      en: 'Total Female members in the family',
      hi: 'परिवार में कुल महिला सदस्य',
      bn: 'পরিবারে মোট মহিলা সদস্য',
      ta: 'குடும்பத்தில் மொத்த பெண் உறுப்பினர்கள்',
      maxDigits: 2,
      maxValue: 20,
    ),

    // Q31: If there are 13-15 year old girls, will you prefer them to join Azad Kishori Program
    QuestionDefinition(
      id: 'girl_13_15_kishori',
      fieldName: 'girl1315Kishori',
      number: 31,
      section: SectionId.basicInfo,
      type: QuestionType.yesNo,
      required: true,
      en: 'If there are 13-15 year old girls in the family will you prefer them to join Azad Kishori Program',
      hi: 'अगर परिवार में 13-15 साल की लड़कियाँ हैं तो क्या आप चाहेंगी कि वे आज़ाद किशोरी कार्यक्रम में शामिल हों',
      bn: 'পরিবারে ১৩-১৫ বছরের মেয়ে থাকলে তাদের কি আজাদ কিশোরী কর্মসূচিতে যোগ দেওয়াতে চান',
      ta: 'குடும்பத்தில் 13-15 வயது சிறுமிகள் இருந்தால் ஆஸாத் கிஷோரி திட்டத்தில் சேர விரும்புவீர்களா',
    ),

    // Q32: How many girls 13-15 (conditional/hidden)
    QuestionDefinition(
      id: 'girls_13_15_count',
      fieldName: 'girls1315Count',
      number: 32,
      section: SectionId.basicInfo,
      type: QuestionType.numberInput,
      required: false,
      en: 'How many girls aged 13-15',
      hi: '13-15 आयु की कितनी लड़कियाँ',
      bn: '১৩-১৫ বছরের কতজন মেয়ে',
      ta: '13-15 வயது சிறுமிகள் எத்தனை',
      maxDigits: 1,
      maxValue: 9,
      conditionalOnField: 'girl1315Kishori',
      conditionalValue: '1',
    ),

    // Q33: How many women in the family who are 18+
    QuestionDefinition(
      id: 'women_18_plus',
      fieldName: 'women18Plus',
      number: 33,
      section: SectionId.basicInfo,
      type: QuestionType.singleSelect,
      required: true,
      en: 'How many women in the family who are 18+',
      hi: 'परिवार में 18+ उम्र की कितनी महिलाएँ हैं',
      bn: 'পরিবারে ১৮+ বয়সের কতজন মহিলা আছে',
      ta: 'குடும்பத்தில் 18+ வயதுடைய பெண்கள் எத்தனை',
      options: [
        QuestionOption(value: 0, en: '0', hi: '0', bn: '0', ta: '0'),
        QuestionOption(value: 1, en: '1', hi: '1', bn: '1', ta: '1'),
        QuestionOption(value: 2, en: '2', hi: '2', bn: '2', ta: '2'),
        QuestionOption(value: 3, en: '3', hi: '3', bn: '3', ta: '3'),
        QuestionOption(value: 4, en: '4', hi: '4', bn: '4', ta: '4'),
        QuestionOption(value: 5, en: '5', hi: '5', bn: '5', ta: '5'),
        QuestionOption(value: 6, en: '6', hi: '6', bn: '6', ta: '6'),
        QuestionOption(value: 7, en: '7', hi: '7', bn: '7', ta: '7'),
        QuestionOption(value: 8, en: '8', hi: '8', bn: '8', ta: '8'),
      ],
    ),
  ];

  // =========================================================================
  // PHASE 2: MEN/BOYS COUNT (kept for backward compat, replaced by Q27)
  // =========================================================================
  static const QuestionDefinition menBoysCountQuestion = QuestionDefinition(
    id: 'men_boys_count',
    fieldName: 'menBoysCount',
    section: SectionId.menBoysCount,
    type: QuestionType.singleSelect,
    required: true,
    en: 'How many men/boys in the family?',
    hi: 'परिवार में कितने पुरुष/लड़के हैं?',
    bn: 'পরিবারে কতজন পুরুষ/ছেলে আছে?',
    ta: 'குடும்பத்தில் எத்தனை ஆண்கள்/சிறுவர்கள்?',
    options: [
      QuestionOption(value: 0, en: '0', hi: '0', bn: '0', ta: '0'),
      QuestionOption(value: 1, en: '1', hi: '1', bn: '1', ta: '1'),
      QuestionOption(value: 2, en: '2', hi: '2', bn: '2', ta: '2'),
      QuestionOption(value: 3, en: '3', hi: '3', bn: '3', ta: '3'),
      QuestionOption(value: 4, en: '4', hi: '4', bn: '4', ta: '4'),
      QuestionOption(value: 5, en: '5', hi: '5', bn: '5', ta: '5'),
      QuestionOption(value: 6, en: '6', hi: '6', bn: '6', ta: '6'),
      QuestionOption(value: 7, en: '7', hi: '7', bn: '7', ta: '7'),
      QuestionOption(value: 8, en: '8', hi: '8', bn: '8', ta: '8'),
    ],
  );

  // =========================================================================
  // PHASE 3: MEN/BOYS DETAILS (repeating per member)
  // =========================================================================
  static const List<QuestionDefinition> menBoysQuestions = [
    QuestionDefinition(
      id: 'mb_name', fieldName: 'name', section: SectionId.menBoysDetails,
      type: QuestionType.textInput, required: true,
      en: 'Name', hi: 'नाम', bn: 'নাম', ta: 'பெயர்',
    ),
    QuestionDefinition(
      id: 'mb_age', fieldName: 'age', section: SectionId.menBoysDetails,
      type: QuestionType.numberInput, required: false, maxDigits: 3,
      en: 'Age', hi: 'उम्र', bn: 'বয়স', ta: 'வயது',
    ),
    QuestionDefinition(
      id: 'mb_education', fieldName: 'education', section: SectionId.menBoysDetails,
      type: QuestionType.textInput, required: false,
      en: 'Education', hi: 'शिक्षा', bn: 'শিক্ষা', ta: 'கல்வி',
    ),
    QuestionDefinition(
      id: 'mb_marital', fieldName: 'marital_status', section: SectionId.menBoysDetails,
      type: QuestionType.singleSelect, required: false,
      en: 'Married / Unmarried', hi: 'विवाहित / अविवाहित', bn: 'বিবাহিত / অবিবাহিত', ta: 'திருமணமானவர் / ஆகாதவர்',
      options: [
        QuestionOption(value: 'Married', en: 'Married', hi: 'विवाहित', bn: 'বিবাহিত', ta: 'திருமணமானவர்'),
        QuestionOption(value: 'Unmarried', en: 'Unmarried', hi: 'अविवाहित', bn: 'অবিবাহিত', ta: 'திருமணமாகாதவர்'),
      ],
    ),
    QuestionDefinition(
      id: 'mb_relation', fieldName: 'relation_with_head', section: SectionId.menBoysDetails,
      type: QuestionType.textInput, required: false,
      en: 'Relation with Head of Family', hi: 'मुखिया से संबंध', bn: 'প্রধানের সাথে সম্পর্ক', ta: 'குடும்பத் தலைவருடன் உறவு',
    ),
    QuestionDefinition(
      id: 'mb_occupation', fieldName: 'occupation', section: SectionId.menBoysDetails,
      type: QuestionType.textInput, required: false,
      en: 'Occupation', hi: 'व्यवसाय', bn: 'পেশা', ta: 'தொழில்',
    ),
    QuestionDefinition(
      id: 'mb_income', fieldName: 'income', section: SectionId.menBoysDetails,
      type: QuestionType.numberInput, required: false, maxDigits: 8,
      en: 'Income', hi: 'आय', bn: 'আয়', ta: 'வருமானம்',
    ),
  ];

  // =========================================================================
  // PHASE 4: WOMEN/GIRLS COUNT (kept for backward compat, replaced by Q30)
  // =========================================================================
  static const QuestionDefinition womenGirlsCountQuestion = QuestionDefinition(
    id: 'women_girls_count',
    fieldName: 'womenGirlsCount',
    section: SectionId.womenGirlsCount,
    type: QuestionType.singleSelect,
    required: true,
    en: 'How many girls/women in the family?',
    hi: 'परिवार में कितनी महिलाएँ/लड़कियाँ हैं?',
    bn: 'পরিবারে কতজন মহিলা/মেয়ে আছে?',
    ta: 'குடும்பத்தில் எத்தனை பெண்கள்/சிறுமிகள்?',
    options: [
      QuestionOption(value: 0, en: '0', hi: '0', bn: '0', ta: '0'),
      QuestionOption(value: 1, en: '1', hi: '1', bn: '1', ta: '1'),
      QuestionOption(value: 2, en: '2', hi: '2', bn: '2', ta: '2'),
      QuestionOption(value: 3, en: '3', hi: '3', bn: '3', ta: '3'),
      QuestionOption(value: 4, en: '4', hi: '4', bn: '4', ta: '4'),
      QuestionOption(value: 5, en: '5', hi: '5', bn: '5', ta: '5'),
      QuestionOption(value: 6, en: '6', hi: '6', bn: '6', ta: '6'),
      QuestionOption(value: 7, en: '7', hi: '7', bn: '7', ta: '7'),
      QuestionOption(value: 8, en: '8', hi: '8', bn: '8', ta: '8'),
    ],
  );

  // =========================================================================
  // PHASE 5: WOMEN/GIRLS DETAILS (repeating per member)
  // =========================================================================
  static const List<QuestionDefinition> womenGirlsQuestions = [
    QuestionDefinition(
      id: 'wg_name', fieldName: 'name', section: SectionId.womenGirlsDetails,
      type: QuestionType.textInput, required: true,
      en: 'Name', hi: 'नाम', bn: 'নাম', ta: 'பெயர்',
    ),
    QuestionDefinition(
      id: 'wg_relation', fieldName: 'relation_with_head', section: SectionId.womenGirlsDetails,
      type: QuestionType.textInput, required: false,
      en: 'Relation with Head of Family', hi: 'मुखिया से संबंध', bn: 'প্রধানের সাথে সম্পর্ক', ta: 'குடும்பத் தலைவருடன் உறவு',
    ),
    QuestionDefinition(
      id: 'wg_age', fieldName: 'age', section: SectionId.womenGirlsDetails,
      type: QuestionType.numberInput, required: false, maxDigits: 3,
      en: 'Age', hi: 'उम्र', bn: 'বয়স', ta: 'வயது',
    ),
    QuestionDefinition(
      id: 'wg_education', fieldName: 'education', section: SectionId.womenGirlsDetails,
      type: QuestionType.textInput, required: false,
      en: 'Education', hi: 'शिक्षा', bn: 'শিক্ষা', ta: 'கல்வி',
    ),
    QuestionDefinition(
      id: 'wg_marital', fieldName: 'marital_status', section: SectionId.womenGirlsDetails,
      type: QuestionType.singleSelect, required: false,
      en: 'Married / Unmarried', hi: 'विवाहित / अविवाहित', bn: 'বিবাহিত / অবিবাহিত', ta: 'திருமணமானவர் / ஆகாதவர்',
      options: [
        QuestionOption(value: 'Married', en: 'Married', hi: 'विवाहित', bn: 'বিবাহিত', ta: 'திருமணமானவர்'),
        QuestionOption(value: 'Unmarried', en: 'Unmarried', hi: 'अविवाहित', bn: 'অবিবাহিত', ta: 'திருமணமாகாதவர்'),
      ],
    ),
    QuestionDefinition(
      id: 'wg_docs', fieldName: 'available_documents', section: SectionId.womenGirlsDetails,
      type: QuestionType.textInput, required: false,
      en: 'Available Documents (Age, Education Proof)', hi: 'उपलब्ध दस्तावेज़ (आयु, शिक्षा प्रमाण)', bn: 'উপলব্ধ নথি (বয়স, শিক্ষা প্রমাণ)', ta: 'கிடைக்கும் ஆவணங்கள் (வயது, கல்வி சான்று)',
    ),
    QuestionDefinition(
      id: 'wg_occupation', fieldName: 'occupation', section: SectionId.womenGirlsDetails,
      type: QuestionType.textInput, required: false,
      en: 'Occupation', hi: 'व्यवसाय', bn: 'পেশা', ta: 'தொழில்',
    ),
    QuestionDefinition(
      id: 'wg_income', fieldName: 'income', section: SectionId.womenGirlsDetails,
      type: QuestionType.numberInput, required: false, maxDigits: 8,
      en: 'Income', hi: 'आय', bn: 'আয়', ta: 'வருமானம்',
    ),
  ];

  // =========================================================================
  // PHASE 6: INTERVIEW ELIGIBLE WOMEN
  // =========================================================================
  static const List<QuestionDefinition> eligibleWomanQuestions = [
    QuestionDefinition(
      id: 'ew_name', fieldName: 'eligibleWomanName', section: SectionId.eligibleWoman,
      type: QuestionType.textInput, required: false,
      en: 'Name of Eligible Woman', hi: 'पात्र महिला का नाम', bn: 'যোগ্য মহিলার নাম', ta: 'தகுதியான பெண்ணின் பெயர்',
    ),
    QuestionDefinition(
      id: 'ew_wants', fieldName: 'eligibleWomanWants', section: SectionId.eligibleWoman,
      type: QuestionType.textInput, required: false,
      en: 'What does she want to do?', hi: 'वह क्या करना चाहती है?', bn: 'তিনি কী করতে চান?', ta: 'அவர் என்ன செய்ய விரும்புகிறார்?',
      keyboardType: QKeyboardType.multiline,
    ),
    QuestionDefinition(
      id: 'ew_obstacles', fieldName: 'eligibleWomanObstacles', section: SectionId.eligibleWoman,
      type: QuestionType.textInput, required: false,
      en: 'What are the obstacles?', hi: 'क्या बाधाएँ हैं?', bn: 'বাধাগুলি কী কী?', ta: 'தடைகள் என்ன?',
      keyboardType: QKeyboardType.multiline,
    ),
    QuestionDefinition(
      id: 'ew_opportunities', fieldName: 'eligibleWomanOpportunities', section: SectionId.eligibleWoman,
      type: QuestionType.textInput, required: false,
      en: 'What opportunities are available?', hi: 'क्या अवसर उपलब्ध हैं?', bn: 'কী সুযোগ পাওয়া যায়?', ta: 'என்ன வாய்ப்புகள் உள்ளன?',
      keyboardType: QKeyboardType.multiline,
    ),
  ];

  // =========================================================================
  // PHASE 6a: ELIGIBLE WOMEN COUNT (NEW — multiple entries)
  // =========================================================================
  static const QuestionDefinition eligibleWomenCountQuestion = QuestionDefinition(
    id: 'eligible_women_count',
    fieldName: 'eligibleWomenCount',
    section: SectionId.eligibleWomenCount,
    type: QuestionType.singleSelect,
    required: true,
    en: 'How many eligible women (for WWW) in the family?',
    hi: 'परिवार में कितनी योग्य महिलाएँ (WWW के लिए) हैं?',
    bn: 'পরিবারে কতজন যোগ্য মহিলা (WWW-এর জন্য) আছে?',
    ta: 'குடும்பத்தில் எத்தனை தகுதியான பெண்கள் (WWW)?',
    options: [
      QuestionOption(value: 0, en: '0', hi: '0', bn: '0', ta: '0'),
      QuestionOption(value: 1, en: '1', hi: '1', bn: '1', ta: '1'),
      QuestionOption(value: 2, en: '2', hi: '2', bn: '2', ta: '2'),
      QuestionOption(value: 3, en: '3', hi: '3', bn: '3', ta: '3'),
      QuestionOption(value: 4, en: '4', hi: '4', bn: '4', ta: '4'),
      QuestionOption(value: 5, en: '5', hi: '5', bn: '5', ta: '5'),
      QuestionOption(value: 6, en: '6', hi: '6', bn: '6', ta: '6'),
      QuestionOption(value: 7, en: '7', hi: '7', bn: '7', ta: '7'),
      QuestionOption(value: 8, en: '8', hi: '8', bn: '8', ta: '8'),
    ],
  );

  // =========================================================================
  // PHASE 6b: ELIGIBLE WOMEN DETAILS (repeating per eligible woman)
  // =========================================================================
  static const List<QuestionDefinition> eligibleWomenDetailQuestions = [
    QuestionDefinition(
      id: 'ew_name', fieldName: 'name', section: SectionId.eligibleWomenDetails,
      type: QuestionType.textInput, required: true,
      en: 'Name of Eligible Woman', hi: 'योग्य महिला का नाम', bn: 'যোগ্য মহিলার নাম', ta: 'தகுதியான பெண்ணின் பெயர்',
    ),
    QuestionDefinition(
      id: 'ew_wants', fieldName: 'wants', section: SectionId.eligibleWomenDetails,
      type: QuestionType.textInput, required: false,
      en: 'What does she want to do?', hi: 'वह क्या करना चाहती है?', bn: 'তিনি কী করতে চান?', ta: 'அவர் என்ன செய்ய விரும்புகிறார்?',
      keyboardType: QKeyboardType.multiline,
    ),
    QuestionDefinition(
      id: 'ew_obstacles', fieldName: 'obstacles', section: SectionId.eligibleWomenDetails,
      type: QuestionType.textInput, required: false,
      en: 'What are the obstacles?', hi: 'क्या बाधाएँ हैं?', bn: 'বাধাগুলি কী কী?', ta: 'தடைகள் என்ன?',
      keyboardType: QKeyboardType.multiline,
    ),
    QuestionDefinition(
      id: 'ew_opportunities', fieldName: 'opportunities', section: SectionId.eligibleWomenDetails,
      type: QuestionType.textInput, required: false,
      en: 'What opportunities are available?', hi: 'क्या अवसर उपलब्ध हैं?', bn: 'কী সুযোগ পাওয়া যায়?', ta: 'என்ன வாய்ப்புகள் உள்ளன?',
      keyboardType: QKeyboardType.multiline,
    ),
  ];

  // =========================================================================
  // PHASE 7: DRIVING INTEREST
  // =========================================================================
  static const List<QuestionDefinition> drivingInterestQuestions = [
    QuestionDefinition(
      id: 'dr_obstacles', fieldName: 'drivingObstacles', section: SectionId.drivingInterest,
      type: QuestionType.textInput, required: false,
      en: 'What obstacles might prevent from joining driving?', hi: 'ड्राइविंग से जुड़ने में क्या बाधाएँ हो सकती हैं?', bn: 'ড্রাইভিংয়ে যোগ দিতে কী বাধা হতে পারে?', ta: 'ஓட்டுநர் பயிற்சியில் சேர என்ன தடைகள்?',
      keyboardType: QKeyboardType.multiline,
    ),
    QuestionDefinition(
      id: 'dr_support', fieldName: 'drivingFamilySupport', section: SectionId.drivingInterest,
      type: QuestionType.textInput, required: false,
      en: 'Who in the family will support you?', hi: 'परिवार में कौन आपका साथ देगा?', bn: 'পরিবারে কে আপনাকে সমর্থন করবে?', ta: 'குடும்பத்தில் யார் உங்களை ஆதரிப்பார்?',
      keyboardType: QKeyboardType.multiline,
    ),
  ];

  // =========================================================================
  // PHASE 8: DOCUMENT CHECKLIST
  // =========================================================================
  static const List<QuestionDefinition> documentQuestions = [
    QuestionDefinition(
      id: 'docs_address', fieldName: 'docsAddressProof', section: SectionId.documents,
      type: QuestionType.multiSelect, required: false,
      en: 'Address Proof', hi: 'पता प्रमाण', bn: 'ঠিকানার প্রমাণ', ta: 'முகவரி சான்று',
      options: [
        QuestionOption(value: 'Ration Card', en: 'Ration Card', hi: 'राशन कार्ड', bn: 'রেশন কার্ড', ta: 'ரேஷன் கார்டு'),
        QuestionOption(value: 'Electricity/Water/Telephone Bill', en: 'Electricity/Water/Telephone Bill', hi: 'बिजली/पानी/टेलीफोन बिल', bn: 'বিদ্যুৎ/জল/টেলিফোন বিল', ta: 'மின்/நீர்/தொலைபேசி பில்'),
        QuestionOption(value: 'Identity Card', en: 'Identity Card', hi: 'पहचान पत्र', bn: 'পরিচয়পত্র', ta: 'அடையாள அட்டை'),
        QuestionOption(value: 'Aadhaar Card', en: 'Aadhaar Card', hi: 'आधार कार्ड', bn: 'আধার কার্ড', ta: 'ஆதார் அட்டை'),
        QuestionOption(value: 'Bank Passbook', en: 'Bank Passbook', hi: 'बैंक पासबुक', bn: 'ব্যাংক পাসবুক', ta: 'வங்கி பாஸ்புக்'),
        QuestionOption(value: 'Driving License', en: 'Driving License', hi: 'ड्राइविंग लाइसेंस', bn: 'ড্রাইভিং লাইসেন্স', ta: 'ஓட்டுநர் உரிமம்'),
      ],
    ),
    QuestionDefinition(
      id: 'docs_age', fieldName: 'docsAgeProof', section: SectionId.documents,
      type: QuestionType.multiSelect, required: false,
      en: 'Age Proof', hi: 'आयु प्रमाण', bn: 'বয়সের প্রমাণ', ta: 'வயது சான்று',
      options: [
        QuestionOption(value: 'School Certificate', en: 'School Certificate', hi: 'स्कूल प्रमाणपत्र', bn: 'স্কুল সার্টিফিকেট', ta: 'பள்ளி சான்றிதழ்'),
        QuestionOption(value: 'T.C.', en: 'T.C. (Transfer Certificate)', hi: 'टी.सी. (स्थानांतरण प्रमाणपत्र)', bn: 'টি.সি. (ট্রান্সফার সার্টিফিকেট)', ta: 'மாற்றுச் சான்றிதழ்'),
        QuestionOption(value: 'Marksheet', en: 'Marksheet', hi: 'अंक पत्र', bn: 'মার্কশিট', ta: 'மதிப்பெண் பட்டியல்'),
        QuestionOption(value: 'PAN Card', en: 'PAN Card', hi: 'पैन कार्ड', bn: 'প্যান কার্ড', ta: 'பான் கார்டு'),
        QuestionOption(value: 'Birth Certificate', en: 'Birth Certificate', hi: 'जन्म प्रमाण पत्र', bn: 'জন্ম সনদ', ta: 'பிறப்புச் சான்றிதழ்'),
      ],
    ),
  ];

  // =========================================================================
  // PHASE 9: REMARKS
  // =========================================================================
  static const QuestionDefinition remarksQuestion = QuestionDefinition(
    id: 'remarks',
    fieldName: 'remarks',
    section: SectionId.remarks,
    type: QuestionType.textInput,
    required: false,
    en: 'Remarks',
    hi: 'टिप्पणी',
    bn: 'মন্তব্য',
    ta: 'கருத்துகள்',
    keyboardType: QKeyboardType.multiline,
  );

  // =========================================================================
  // V1 LEGACY — kept for backward compatibility with old survey_women
  // =========================================================================
  static const List<QuestionDefinition> mainQuestions = [];
  static const QuestionDefinition commentQuestion = QuestionDefinition(
    id: 'comment', fieldName: 'comment', section: SectionId.main,
    type: QuestionType.textInput, required: false,
    en: 'Comments', hi: 'टिप्पणी', bn: 'মন্তব্য', ta: 'கருத்துகள்',
    keyboardType: QKeyboardType.multiline,
  );
  static const List<QuestionDefinition> womenQuestions = [];

  // =========================================================================
  // HELPER METHODS
  // =========================================================================

  static List<QuestionDefinition> getBasicInfoQuestions() => basicInfoQuestions;
  static List<QuestionDefinition> getMenBoysQuestions() => menBoysQuestions;
  static List<QuestionDefinition> getWomenGirlsQuestions() => womenGirlsQuestions;
  static List<QuestionDefinition> getEligibleWomanQuestions() => eligibleWomanQuestions;
  static List<QuestionDefinition> getEligibleWomenDetailQuestions() => eligibleWomenDetailQuestions;
  static List<QuestionDefinition> getDrivingInterestQuestions() => drivingInterestQuestions;
  static List<QuestionDefinition> getDocumentQuestions() => documentQuestions;

  /// Returns all questions for review screen (non-repeating phases only).
  static List<QuestionDefinition> getAllBasicQuestions() {
    return [
      ...basicInfoQuestions,
    ];
  }

  static String getSectionTitle(SectionId section, String locale) {
    switch (section) {
      case SectionId.basicInfo:
        return _t(locale, 'Basic Information', 'बुनियादी जानकारी', 'মৌলিক তথ্য', 'அடிப்படை தகவல்');
      case SectionId.menBoysCount:
      case SectionId.menBoysDetails:
        return _t(locale, 'Men / Boys Details', 'पुरुष / लड़के विवरण', 'পুরুষ / ছেলেদের বিবরণ', 'ஆண்கள் / சிறுவர்கள் விவரங்கள்');
      case SectionId.womenGirlsCount:
      case SectionId.womenGirlsDetails:
        return _t(locale, 'Girls / Women Details', 'लड़कियाँ / महिला विवरण', 'মেয়ে / মহিলাদের বিবরণ', 'பெண்கள் / சிறுமிகள் விவரங்கள்');
      case SectionId.eligibleWoman:
        return _t(locale, 'Interview Eligible Women', 'पात्र महिला साक्षात्कार', 'যোগ্য মহিলার সাক্ষাৎকার', 'தகுதியான பெண் நேர்காணல்');
      case SectionId.eligibleWomenCount:
        return _t(locale, 'Eligible Women Count', 'योग्य महिलाओं की संख्या', 'যোগ্য মহিলার সংখ্যা', 'தகுதியான பெண்களின் எண்ணிக்கை');
      case SectionId.eligibleWomenDetails:
        return _t(locale, 'Eligible Women Details', 'योग्य महिला विवरण', 'যোগ্য মহিলার বিবরণ', 'தகுதியான பெண் விவரங்கள்');
      case SectionId.drivingInterest:
        return _t(locale, 'Driving Interest', 'ड्राइविंग में रुचि', 'ড্রাইভিংয়ে আগ্রহ', 'ஓட்டுநர் ஆர்வம்');
      case SectionId.documents:
        return _t(locale, 'Document Checklist', 'दस्तावेज़ चेकलिस्ट', 'নথি তালিকা', 'ஆவண சரிபார்ப்பு');
      case SectionId.remarks:
        return _t(locale, 'Remarks', 'टिप्पणी', 'মন্তব্য', 'கருத்துகள்');
      case SectionId.main:
        return _t(locale, 'Household Survey', 'घरेलू सर्वेक्षण', 'পারিবারিক সমীক্ষা', 'குடும்ப கணக்கெடுப்பு');
      case SectionId.womenDetails:
        return _t(locale, 'Women Details (18+)', 'महिला विवरण (18+)', 'মহিলার বিবরণ (১৮+)', 'பெண் விவரங்கள் (18+)');
    }
  }

  static String _t(String locale, String en, String hi, String bn, String ta) {
    switch (locale) {
      case 'hi': return hi;
      case 'bn': return bn;
      case 'ta': return ta;
      default: return en;
    }
  }
}
