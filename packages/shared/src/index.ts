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
  Anomaly_Score: z.number().optional(),
  Reason: z.string().optional()
});

export type TestRecord = z.infer<typeof TestRecordSchema>;

export const AttentionDetailSchema = z.object({
  test_id: z.string(),
  anomaly_score: z.number(),
  validity: z.string(),
  predicted_ref: z.number(),
  reason: z.string()
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
  explanation_word_count: z.number()
});

export type AutomatedSummary = z.infer<typeof AutomatedSummarySchema>;
