# Sage ANN Training Review

Train rows: 30729; validation rows: 3841; features: 8000.

The test set was not loaded. Labels are supplied by the source dataset and contain known noise.

## Validation comparison

| model | accuracy | macro_f1 | macro_recall | negative_f1 | neutral_f1 | positive_f1 | best_epoch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| weighted_regularized_ann | 0.7688 | 0.61 | 0.6409 | 0.7696 | 0.2105 | 0.85 | 3 |
| regularized_ann | 0.8237 | 0.6074 | 0.5962 | 0.7915 | 0.1521 | 0.8786 | 4 |
| baseline_ann | 0.8243 | 0.6018 | 0.5932 | 0.7943 | 0.135 | 0.8762 | 3 |

## Class weights

{
  "0": 0.9283966282969274,
  "1": 6.930311231393776,
  "2": 0.5622461302009002
}

## baseline_ann

| index | precision | recall | f1-score | support |
| --- | --- | --- | --- | --- |
| Negative | 0.8034 | 0.7854 | 0.7943 | 1379.0 |
| Neutral | 0.3077 | 0.0865 | 0.135 | 185.0 |
| Positive | 0.8468 | 0.9078 | 0.8762 | 2277.0 |
| accuracy | 0.8243 | 0.8243 | 0.8243 | 0.8243 |
| macro avg | 0.6526 | 0.5932 | 0.6018 | 3841.0 |
| weighted avg | 0.8052 | 0.8243 | 0.8111 | 3841.0 |

### Training history

| epoch | accuracy | loss | val_accuracy | val_loss | val_macro_f1 | learning_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.7921 | 0.6299 | 0.8282 | 0.4721 | 0.5572 | 0.001 |
| 2 | 0.8628 | 0.3791 | 0.8292 | 0.4779 | 0.5877 | 0.001 |
| 3 | 0.8954 | 0.2976 | 0.8243 | 0.5334 | 0.6018 | 0.001 |
| 4 | 0.9222 | 0.2291 | 0.8118 | 0.5989 | 0.5982 | 0.001 |
| 5 | 0.9414 | 0.1782 | 0.8063 | 0.6867 | 0.5924 | 0.001 |
| 6 | 0.9557 | 0.1388 | 0.8066 | 0.7378 | 0.5956 | 0.0005 |
| 7 | 0.9607 | 0.1245 | 0.8055 | 0.7914 | 0.5944 | 0.0005 |

## regularized_ann

| index | precision | recall | f1-score | support |
| --- | --- | --- | --- | --- |
| Negative | 0.8258 | 0.76 | 0.7915 | 1379.0 |
| Neutral | 0.2564 | 0.1081 | 0.1521 | 185.0 |
| Positive | 0.8404 | 0.9205 | 0.8786 | 2277.0 |
| accuracy | 0.8237 | 0.8237 | 0.8237 | 0.8237 |
| macro avg | 0.6409 | 0.5962 | 0.6074 | 3841.0 |
| weighted avg | 0.8071 | 0.8237 | 0.8124 | 3841.0 |

### Training history

| epoch | accuracy | loss | val_accuracy | val_loss | val_macro_f1 | learning_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.7756 | 0.6616 | 0.8269 | 0.4927 | 0.5562 | 0.001 |
| 2 | 0.8538 | 0.4352 | 0.831 | 0.5008 | 0.5706 | 0.001 |
| 3 | 0.879 | 0.3804 | 0.825 | 0.5407 | 0.5851 | 0.001 |
| 4 | 0.9008 | 0.334 | 0.8237 | 0.5741 | 0.6074 | 0.001 |
| 5 | 0.9176 | 0.295 | 0.8209 | 0.6103 | 0.6012 | 0.001 |
| 6 | 0.9294 | 0.2667 | 0.8175 | 0.6516 | 0.5964 | 0.001 |
| 7 | 0.9423 | 0.2335 | 0.8193 | 0.6764 | 0.6026 | 0.0005 |
| 8 | 0.9493 | 0.2136 | 0.8196 | 0.7002 | 0.6074 | 0.0005 |

## weighted_regularized_ann

| index | precision | recall | f1-score | support |
| --- | --- | --- | --- | --- |
| Negative | 0.8134 | 0.7302 | 0.7696 | 1379.0 |
| Neutral | 0.1475 | 0.3676 | 0.2105 | 185.0 |
| Positive | 0.8768 | 0.8248 | 0.85 | 2277.0 |
| accuracy | 0.7688 | 0.7688 | 0.7688 | 0.7688 |
| macro avg | 0.6126 | 0.6409 | 0.61 | 3841.0 |
| weighted avg | 0.8189 | 0.7688 | 0.7903 | 3841.0 |

### Training history

| epoch | accuracy | loss | val_accuracy | val_loss | val_macro_f1 | learning_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.6606 | 0.9223 | 0.7175 | 0.7502 | 0.5891 | 0.001 |
| 2 | 0.7872 | 0.6642 | 0.7423 | 0.7156 | 0.6009 | 0.001 |
| 3 | 0.8354 | 0.5331 | 0.7688 | 0.6881 | 0.61 | 0.001 |
| 4 | 0.8682 | 0.441 | 0.7607 | 0.7229 | 0.6011 | 0.001 |
| 5 | 0.8903 | 0.3826 | 0.7725 | 0.728 | 0.6038 | 0.001 |
| 6 | 0.9114 | 0.3274 | 0.7837 | 0.7182 | 0.6093 | 0.0005 |
| 7 | 0.9203 | 0.3044 | 0.787 | 0.7167 | 0.6013 | 0.0005 |

## Selected model

weighted_regularized_ann

## Sample validation errors

| index | text | sentiment | company | predicted |
| --- | --- | --- | --- | --- |
| 1181 | طول اليوم بره البيت | positive | talbat | Negative |
| 1888 | التوصيل غالي والطلبيه تتاخر | negative | talbat | Neutral |
| 148 | انا بالمدينه واجاني بس مطعم واحد ياليت توفرون مطاعم اكتر | negative | talbat | Positive |
| 1815 | هوحلو بس ان معند شريح 😢😢 | positive | talbat | Neutral |
| 2618 | جيد جاني الطلب خلال16 دقيقه ولاكن توقعا | positive | talbat | Neutral |
| 3496 | 8 ظن ٩خخ0ظ8 | negative | talbat | Neutral |
| 1445 | ارجو الرد علي المساعده موراضي ينزل | negative | talbat | Positive |
| 3605 | بس ناقص لو يصير تطلب من اكثر من طلب | positive | talbat | Neutral |
| 2601 | ما طلبت شيء بس اشوف يعني اكيد تطبيق حلو | positive | talbat | Neutral |
| 2418 | جيد لكن يحتاج دعم من ناحية الصور | positive | talbat | Neutral |
| 3429 | 🤮🤮🤮🤮🤮🤮🤮🤮🤮🤮🤮🤮🤮🤮 | negative | talbat | Positive |
| 518 | كيف رح اشغلو ما عم يشتغل | positive | swvl | Negative |
| 2795 | وقت التوصيل طويل | neutral | talbat | Negative |
| 268 | اتمني اضافه خدمه تحديد الموقع من قوقل | positive | talbat | Neutral |
| 3149 | هو ليه لو انا مسافر مينفعش احجز غير مكانين بس عايزه احجز اكتر من مكان | negative | swvl | Neutral |
| 2258 | الخدمه واقفه وعاوزة اروح شغلي نعمل ايه | negative | swvl | Neutral |
| 2449 | من الكلام الي سمعنا مو كويس | negative | talbat | Neutral |
| 2384 | يطولون شوي وفيه واحد سوداني باقي لي عنده ١٥ ريال بس يضل احسن برنامج توصيل | neutral | talbat | Positive |
| 3535 | عقب التحديث الجديد لاتظهر ايقونه الكاميرا اثناء التحدث مع الموظفين في حال حدوث مشكله وطلب الموظف ارسال صوره نتمني تعديل الخلل | negative | talbat | Positive |
| 3229 | تطبيق جيد جدا لكن مايفتح عندي مجرد ادخل علي التطبيق ومايفتح ليش؟ وهل يوجد توصيل للعراق ؟ ارجو الرد | positive | talbat | Neutral |
| 261 | التطبيق مش بيفتح ارجو حل المشكله بسرعه | negative | telecom_egypt | Neutral |
| 630 | لا درت عليهم همه ما بعرفو طبلبو بس انا ما بعرف كيف اطلب | positive | talbat | Neutral |
| 787 | لا يوجد مصداقيه في التوقيت عامل الوقت غير مهم بالنسبه لكم تجربة سيئه لا انصح في استخدام البرنامج خدمة العملاء لديكم ممله بسبب كثرة الاعتذار | neutral | talbat | Negative |
| 1238 | شباب دوبي مسحتو عشان ما طلعلي (اختر المدينة) اضغط اي شي مايصير بس برجع احملو | positive | talbat | Negative |
| 2626 | هل يوجد توصيل الطلبات فالامارات؟! | positive | talbat | Neutral |
| 116 | بس لو تترتب العروض ف العرض | positive | talbat | Neutral |
| 1221 | جميل لكن ياريت تخلو المطاعم توصل لكل المناطق | negative | talbat | Neutral |
| 1276 | ولله واووو وشكر الي يطلع البرنامج | positive | talbat | Negative |
| 2676 | هو كان عجبني جدا بس حصلت مشكله طلبت اردر وبعد ساعه اتصل بيا قالي الطلب مش موجود في المطعم اتخنقت معاهم ومن سعتها التطبيق مش راضي يشتغل عندي بعت كتير ولسه مش شغال | positive | talbat | Negative |
| 2748 | المطاعم ترفع اسعارهم من اجل التوصيل | negative | talbat | Neutral |

## Saved bundle

E:\ANN\ANN_01\results_dl\ann_runs\20261124_145934_053449\selected_bundle

## Interpretation

Class weights can trade precision for recall. They do not fix annotation errors. Model selection is based on validation macro F1. Final test evaluation belongs in Notebook 03.