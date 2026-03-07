import React from "react";
import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface StatusBadgeProps {
  status: "pending" | "in_progress" | "completed";
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const { t } = useTranslation();

  const statusMap = {
    pending: { label: t("pending"), color: "warning" as const },
    in_progress: { label: t("inProgress"), color: "info" as const },
    completed: { label: t("completed"), color: "success" as const },
  };

  return (
    <Chip
      label={statusMap[status].label}
      color={statusMap[status].color}
      size="small"
    />
  );
};

export default StatusBadge;
