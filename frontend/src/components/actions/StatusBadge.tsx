import React from "react";
import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface StatusBadgeProps {
  status: string;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const { t } = useTranslation();

  const statusStr = typeof status === 'string' ? status : 'pending';
  const normalizedStatus = statusStr.toLowerCase();

  const getLabel = (key: string, defaultText: string) => {
    const val = t(key, defaultText);
    return typeof val === 'string' ? val : defaultText;
  };

  const statusMap: Record<string, { label: string; color: "warning" | "info" | "success" | "error" | "default" }> = {
    pending: { label: getLabel("common.pending", "Pending"), color: "warning" },
    in_progress: { label: getLabel("common.in_progress", "In Progress"), color: "info" },
    completed: { label: getLabel("common.completed", "Completed"), color: "success" },
    cancelled: { label: getLabel("common.cancelled", "Cancelled"), color: "error" },
    overdue: { label: getLabel("common.overdue", "Overdue"), color: "error" }
  };

  const config = statusMap[normalizedStatus] || { label: statusStr, color: "default" };

  return (
    <Chip
      label={config.label || "Unknown"}
      color={config.color}
      size="small"
    />
  );
};

export default StatusBadge;
