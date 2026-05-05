/**
 * Frontend Audit Service
 * 
 * Logs critical user actions (CREATE, UPDATE, DELETE) for ISO 27001 compliance.
 * Works in conjunction with backend AuditMiddleware for complete audit trail.
 * 
 * Usage:
 *   await auditService.logAction("CREATE", "meetings", { meetingId: "123" });
 *   await auditService.logAction("DELETE", "actions", { recordId: "456" });
 */

import api from "./api";

export interface AuditPayload {
  action: "CREATE" | "READ" | "UPDATE" | "DELETE" | "LOGIN" | "LOGOUT";
  resource: string; // e.g., "meetings", "actions", "team", "auth"
  recordId?: string;
  details?: Record<string, unknown>;
}

class AuditService {
  /**
   * Log an action for audit trail
   * Frontend sends to backend which persists to audit_log table
   */
  async logAction(payload: AuditPayload): Promise<void> {
    try {
      // Send audit log to backend
      // Backend endpoint captures it with user context, client_id, IP, user-agent
      await api.post("/audit/log", {
        action: payload.action,
        resource: payload.resource,
        record_id: payload.recordId,
        details: payload.details,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      // Log error but don't throw - audit failure shouldn't break main flow
      console.error("Audit logging failed:", error);
      // In production, could send to error tracking service
    }
  }

  /**
   * Log a create action (POST)
   */
  async logCreate(resource: string, recordId: string, details?: Record<string, unknown>): Promise<void> {
    return this.logAction({
      action: "CREATE",
      resource,
      recordId,
      details,
    });
  }

  /**
   * Log an update action (PATCH/PUT)
   */
  async logUpdate(resource: string, recordId: string, details?: Record<string, unknown>): Promise<void> {
    return this.logAction({
      action: "UPDATE",
      resource,
      recordId,
      details,
    });
  }

  /**
   * Log a delete action (DELETE)
   */
  async logDelete(resource: string, recordId: string, details?: Record<string, unknown>): Promise<void> {
    return this.logAction({
      action: "DELETE",
      resource,
      recordId,
      details,
    });
  }

  /**
   * Log a login action
   */
  async logLogin(userId: string, clientId: string): Promise<void> {
    return this.logAction({
      action: "LOGIN",
      resource: "auth",
      recordId: userId,
      details: { clientId },
    });
  }

  /**
   * Log a logout action
   */
  async logLogout(userId: string, clientId: string): Promise<void> {
    return this.logAction({
      action: "LOGOUT",
      resource: "auth",
      recordId: userId,
      details: { clientId },
    });
  }
}

export const auditService = new AuditService();
export default auditService;
