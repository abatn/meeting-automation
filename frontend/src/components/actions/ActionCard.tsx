import React from "react";
import { ListItem, ListItemText, Chip } from "@mui/material";
import { useTranslation } from "react-i18next";
import StatusBadge from "./StatusBadge"; // Assuming StatusBadge is in the same directory

interface Action {
  id: number;
  description: string;
  assignee: string;
  dueDate: string;
  status: "pending" | "in_progress" | "completed";
}

interface ActionCardProps {
  action: Action;
}

const ActionCard: React.FC<ActionCardProps> = ({ action }) => {
  const { t } = useTranslation();
  return (
    <ListItem>
      <ListItemText
        primary={action.description}
        secondary={t('actions.assignee_and_due', { assignee: action.assignee, due: new Date(action.dueDate).toLocaleDateString() })}
      />
      <StatusBadge status={action.status} />
    </ListItem>
  );
};

export default ActionCard;
