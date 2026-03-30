import React from "react";
import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface StatusBadgeProps {
  status: string;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const { t } = useTranslation();

  const normalizedStatus = (status || 'pending').toLowerCase() as "pending" | "in_progress" | "completed";

  const statusMap = {
    pending: { label: t("common.pending"), color: "warning" as const },
    in_progress: { label: t("common.in_progress"), color: "info" as const },
    completed: { label: t("common.completed"), color: "success" as const },
  };

  const config = statusMap[normalizedStatus] || statusMap.pending;

  return (
    <Chip
      label={config.label}
      color={config.color}
      size="small"
    />
  );
};

export default StatusBadge;
