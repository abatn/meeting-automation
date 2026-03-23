import React, { useState, useEffect } from "react";
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
  CircularProgress,
} from "@mui/material";
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  WhatsApp as WhatsAppIcon,
  MoreVert as MoreIcon,
  CheckCircle as CompleteIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { RootState } from "../../store";
import api from "../../services/api";
import StatusBadge from "./StatusBadge";

const ActionTracker: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [actions, setActions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useSelector((state: RootState) => state.auth);

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const response = await api.get('/actions/my-actions');
        setActions(response.data);
      } catch (error) {
        console.error('Failed to fetch actions:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchActions();
  }, []);

  const handleWhatsAppReminder = (owner: string) => {
    console.log(`Sending WhatsApp reminder to ${owner}`);
  };

  const handleComplete = async (id: string) => {
    try {
      await api.patch(`/actions/${id}/status`, { status: "completed" });
      setActions(actions.map(a => a.id === id ? { ...a, status: "completed" } : a));
    } catch (error) {
      console.error('Failed to complete action:', error);
    }
  };

  const filteredActions = actions.filter((action) =>
    action.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

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

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}>
          <CircularProgress />
        </Box>
      ) : (
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
              {filteredActions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                    {t('dashboard.no_actions_found') || "No actions found."}
                  </TableCell>
                </TableRow>
              ) : (
                filteredActions.map((action) => (
                  <TableRow key={action.id} hover>
                    <TableCell sx={{ fontWeight: "medium" }}>
                      {action.title}
                    </TableCell>
                    <TableCell>{user?.full_name || t('common.me')}</TableCell>
                    <TableCell>
                      <Chip
                        label={action.priority || 'Medium'}
                        size="small"
                        color={action.priority?.toLowerCase() === "high" ? "error" : "warning"}
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={action.status || 'pending'} />
                    </TableCell>
                    <TableCell>{action.due_date ? new Date(action.due_date).toLocaleDateString() : 'N/A'}</TableCell>
                    <TableCell align="right">
                      <IconButton
                        color="success"
                        onClick={() => handleWhatsAppReminder(user?.full_name || 'Me')}
                        title={t("common.actions")}
                      >
                        <WhatsAppIcon fontSize="small" />
                      </IconButton>
                      <IconButton 
                        color="primary" 
                        onClick={() => handleComplete(action.id)}
                        disabled={action.status === 'completed'}
                      >
                        <CompleteIcon fontSize="small" />
                      </IconButton>
                      <IconButton>
                        <MoreIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

export default ActionTracker;
