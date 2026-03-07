import React, { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  TextField,
  InputAdornment,
  Button,
  IconButton,
  Menu,
  MenuItem,
} from "@mui/material";
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  WhatsApp as WhatsAppIcon,
  MoreVert as MoreIcon,
  CheckCircle as CompleteIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import StatusBadge from "./StatusBadge";

const ActionTracker: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");

  const actions: Array<{
    id: number;
    title: string;
    owner: string;
    priority: string;
    status: "pending" | "completed" | "in_progress";
    due: string;
  }> = [
    {
      id: 1,
      title: t("actions.mock_fix_bug"),
      owner: "Sami Ben Ali",
      priority: "High",
      status: "pending",
      due: "2026-02-21",
    },
    {
      id: 2,
      title: t("actions.mock_update_docs"),
      owner: "Amel Trabelsi",
      priority: "Medium",
      status: "completed",
      due: "2026-02-25",
    },
    {
      id: 3,
      title: t("actions.mock_client_prep"),
      owner: "Mohamed Mahmoud",
      priority: "High",
      status: "pending",
      due: "2026-02-19",
    },
  ];

  const handleWhatsAppReminder = (owner: string) => {
    console.log(`Sending WhatsApp reminder to ${owner}`);
    // Simulation of WhatsApp integration logic
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        {t("actions.tracker_title")}
      </Typography>

      <Paper
        sx={{ mb: 3, p: 2, display: "flex", gap: 2, alignItems: "center" }}
      >
        <TextField
          size="small"
          placeholder={t("common.search")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ flexGrow: 1 }}
        />
        <Button startIcon={<FilterIcon />} variant="outlined">
          {t("common.filter")}
        </Button>
        <Button variant="contained" color="primary">
          {t("actions.export")}
        </Button>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: "action.hover" }}>
            <TableRow>
              <TableCell>{t("actions.title")}</TableCell>
              <TableCell>{t("actions.owner")}</TableCell>
              <TableCell>{t("actions.priority")}</TableCell>
              <TableCell>{t("actions.status")}</TableCell>
              <TableCell>{t("actions.due_date")}</TableCell>
              <TableCell align="right">{t("common.actions")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {actions.map((action) => (
              <TableRow key={action.id} hover>
                <TableCell sx={{ fontWeight: "medium" }}>
                  {action.title}
                </TableCell>
                <TableCell>{action.owner}</TableCell>
                <TableCell>
                  <Chip
                    label={t(
                      `actions.priority_${action.priority.toLowerCase()}`,
                      action.priority,
                    )}
                    size="small"
                    color={action.priority === "High" ? "error" : "warning"}
                  />
                </TableCell>
                <TableCell>
                  <StatusBadge status={action.status} />
                </TableCell>
                <TableCell>{action.due}</TableCell>
                <TableCell align="right">
                  <IconButton
                    color="success"
                    onClick={() => handleWhatsAppReminder(action.owner)}
                    title="Send WhatsApp Reminder"
                  >
                    <WhatsAppIcon fontSize="small" />
                  </IconButton>
                  <IconButton color="primary">
                    <CompleteIcon fontSize="small" />
                  </IconButton>
                  <IconButton>
                    <MoreIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default ActionTracker;
