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
  Sensor_S4: z.number().nullable().optional()
});

export type TestRecord = z.infer<typeof TestRecordSchema>;
