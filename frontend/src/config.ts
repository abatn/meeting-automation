import { z } from 'zod';

// ── Server-side guard ───────────────────────────────────────────────
const serverEnv = typeof window === 'undefined';
if (serverEnv && process.env.NODE_ENV === 'production') {
  if (!process.env.POSTGRES_URL) {
    throw new Error(
      'Missing POSTGRES_URL — required in production server environment'
    );
  }
}

// ── Schema ──────────────────────────────────────────────────────────
const databaseSchema = z.object({
  host: z.string().default('localhost'),
  port: z.coerce.number().int().positive().default(5432),
  name: z.string().default('meeting_db_staging'),
  user: z.string().default('meeting_user'),
  password: z.string().default('meeting_password'),
  ssl: z.coerce.boolean().default(false),
});

const apiSchema = z.object({
  port: z.coerce.number().int().positive().default(8000),
  host: z.string().default('localhost'),
  baseUrl: z.string().url().default('http://localhost:8000'),
  timeout: z.coerce.number().int().positive().default(10000),
});

const authSchema = z.object({
  secret: z.string().default('dev-secret-change-in-production'),
  algorithm: z
    .enum(['HS256', 'HS384', 'HS512'])
    .default('HS256'),
  accessTokenExpiry: z.string().default('15m'),
  refreshTokenExpiry: z.string().default('7d'),
});

const redisSchema = z.object({
  url: z.string().url().default('redis://localhost:6379'),
});

const minioSchema = z.object({
  endpoint: z.string().default('localhost'),
  port: z.coerce.number().int().positive().default(9000),
  accessKey: z.string().default('minio_user'),
  secretKey: z.string().default('minio_password'),
  bucket: z.string().default('meeting-recordings-staging'),
  useSsl: z.coerce.boolean().default(false),
});

const corsSchema = z.object({
  origin: z.string().default('http://localhost:3000'),
  credentials: z.coerce.boolean().default(true),
});

const loggingSchema = z.object({
  level: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  format: z.enum(['json', 'text']).default('json'),
});

const nodeEnvSchema = z
  .enum(['development', 'production', 'test'])
  .default('development');

// ── Infer types ─────────────────────────────────────────────────────
export type DatabaseConfig = z.infer<typeof databaseSchema>;
export type ApiConfig = z.infer<typeof apiSchema>;
export type AuthConfig = z.infer<typeof authSchema>;
export type RedisConfig = z.infer<typeof redisSchema>;
export type MinioConfig = z.infer<typeof minioSchema>;
export type CorsConfig = z.infer<typeof corsSchema>;
export type LoggingConfig = z.infer<typeof loggingSchema>;

// ── Build config ────────────────────────────────────────────────────
const rawConfig = {
  nodeEnv: nodeEnvSchema.parse(process.env.NODE_ENV),
  database: databaseSchema.parse({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    name: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    ssl: process.env.DB_SSL,
  }),
  api: apiSchema.parse({
    port: process.env.API_PORT,
    host: process.env.API_HOST,
    baseUrl: process.env.API_BASE_URL,
    timeout: process.env.API_TIMEOUT,
  }),
  auth: authSchema.parse({
    secret: process.env.JWT_SECRET,
    algorithm: process.env.JWT_ALGORITHM,
    accessTokenExpiry: process.env.JWT_ACCESS_EXPIRY,
    refreshTokenExpiry: process.env.JWT_REFRESH_EXPIRY,
  }),
  redis: redisSchema.parse({
    url: process.env.REDIS_URL,
  }),
  minio: minioSchema.parse({
    endpoint: process.env.MINIO_ENDPOINT,
    port: process.env.MINIO_PORT,
    accessKey: process.env.MINIO_ACCESS_KEY,
    secretKey: process.env.MINIO_SECRET_KEY,
    bucket: process.env.MINIO_BUCKET,
    useSsl: process.env.MINIO_USE_SSL,
  }),
  cors: corsSchema.parse({
    origin: process.env.CORS_ORIGIN,
    credentials: process.env.CORS_CREDENTIALS,
  }),
  logging: loggingSchema.parse({
    level: process.env.LOG_LEVEL,
    format: process.env.LOG_FORMAT,
  }),
} as const;

// ── Validate cross-field constraints ────────────────────────────────
if (
  rawConfig.nodeEnv === 'production' &&
  rawConfig.auth.secret === 'dev-secret-change-in-production'
) {
  throw new Error(
    'JWT_SECRET must be changed in production — dev default is not allowed'
  );
}

// ── Export frozen config ────────────────────────────────────────────
export const config = Object.freeze(rawConfig);
export default config;
