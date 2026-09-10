import { z } from 'zod';

export const TestRecordSchema = z.object({
  Test_ID: z.string(),
  Applied_Voltage_kV: z.number(),
  Load_Current_A: z.number(),
  Ambient_Temperature_C: z.number(),
  Test_Duration_min: z.number(),
  Sensor_S1: z.number().nullable().optional(),
  Sensor_S2: z.number().nullable().optional(),
  Sensor_S3: z.number().nullable().optional(),
  Sensor_S4: z.number().nullable().optional(),
  Reference_Parameter: z.number().nullable().optional(),
  Validity_Label: z.enum(['Valid', 'Invalid']).nullable().optional(),
  Predicted_Reference_Parameter: z.number().optional(),
  Interval_95_Lower: z.number().optional(),
  Interval_95_Upper: z.number().optional(),
  Interval_Width: z.number().optional(),
  Interval_Margin: z.number().optional(),
  Anomaly_Score: z.number().optional(),
  Reason: z.string().optional(),
  Fault_Detected: z.boolean().optional(),
  Fault_Type: z.string().optional(),
  Fault_Sensor: z.string().optional(),
  Fault_Severity: z.string().optional(),
  Fault_Reason: z.string().optional(),
  Fault_Confidence: z.string().optional(),
  Mahalanobis_Distance: z.number().optional(),
  Cross_Sensor_Inconsistent: z.boolean().optional(),
  Contributing_Sensors: z.string().optional(),
  Multivariate_Anomaly_Score: z.number().optional(),
  S1_Residual: z.number().optional(),
  S2_Residual: z.number().optional(),
  S3_Residual: z.number().optional()
});

export type TestRecord = z.infer<typeof TestRecordSchema>;

export const AttentionDetailSchema = z.object({
  test_id: z.string(),
  anomaly_score: z.number(),
  validity: z.string(),
  predicted_ref: z.number(),
  reason: z.string(),
  fault_type: z.string().optional(),
  fault_sensor: z.string().optional(),
  fault_severity: z.string().optional(),
  fault_confidence: z.string().optional()
});

export type AttentionDetail = z.infer<typeof AttentionDetailSchema>;

export const AutomatedSummarySchema = z.object({
  number_of_records_analysed: z.number(),
  number_of_abnormal_records_identified: z.number(),
  minimum_predicted_reference_parameter: z.number(),
  maximum_predicted_reference_parameter: z.number(),
  average_predicted_reference_parameter: z.number(),
  three_test_ids_requiring_highest_attention: z.array(z.string()),
  top_three_attention_details: z.array(AttentionDetailSchema),
  methodology_explanation: z.string(),
  explanation_word_count: z.number(),
  conformal_prediction_margin_deg_C: z.number().optional(),
  conformal_interval_width_deg_C: z.number().optional(),
  conformal_calibration: z.record(z.string(), z.any()).optional(),
  fault_type_distribution: z.record(z.string(), z.number()).optional(),
  cross_sensor_inconsistent_count: z.number().optional()
});

export type AutomatedSummary = z.infer<typeof AutomatedSummarySchema>;

export const BenchmarkItemSchema = z.object({
  model: z.string(),
  r2_score: z.number(),
  rmse: z.number(),
  mae: z.number(),
  status: z.string()
});

export type BenchmarkItem = z.infer<typeof BenchmarkItemSchema>;

export const BenchmarkResultSchema = z.object({
  total_verified_records: z.number(),
  cross_validation_folds: z.number(),
  benchmark_table: z.array(BenchmarkItemSchema),
  champion_model: z.string(),
  conformal_interval_margin_deg_C: z.number().optional(),
  feature_group_ablation: z.array(z.record(z.string(), z.any())).optional()
});

export type BenchmarkResult = z.infer<typeof BenchmarkResultSchema>;

export const SHAPDriverSchema = z.object({
  feature: z.string(),
  delta_deg_C: z.number()
});

export const SHAPExplanationSchema = z.object({
  test_id: z.string(),
  base_value: z.number(),
  contributions: z.record(z.string(), z.number()),
  top_positive: z.array(SHAPDriverSchema),
  top_negative: z.array(SHAPDriverSchema)
});

export type SHAPExplanation = z.infer<typeof SHAPExplanationSchema>;
