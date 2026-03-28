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
  alpha,
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
    action.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
    action.status?.toLowerCase() !== "completed"
  );

  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1400, mx: "auto" }}>
      
      {/* HEADER */}
      <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary", mb: 4 }}>
        {t("actions.tracker_title")}
      </Typography>

      {/* TOOLBAR */}
      <Paper
        variant="outlined"
        sx={{ mb: 4, p: 2, display: "flex", gap: 2, alignItems: "center", borderRadius: 3, borderColor: "divider" }}
      >
        <TextField
          size="small"
          placeholder={t("common.search")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 20, color: "text.secondary" }} />
              </InputAdornment>
            ),
            sx: { borderRadius: 2, fontSize: 14 }
          }}
          sx={{ flexGrow: 1 }}
        />
        <Button 
          startIcon={<FilterIcon sx={{ fontSize: 18 }} />} 
          variant="outlined"
          sx={{ 
            borderRadius: 2, 
            borderColor: "divider", 
            color: "text.primary", 
            textTransform: "none",
            fontSize: 14,
            fontWeight: 500,
            px: 3,
            "&:hover": { borderColor: "text.primary", bgcolor: "transparent" }
          }}
        >
          {t("common.filter")}
        </Button>
        <Button 
          variant="contained" 
          disableElevation
          sx={{ 
            bgcolor: "#000", 
            color: "#FFF", 
            borderRadius: 2, 
            textTransform: "none",
            fontSize: 14,
            fontWeight: 600,
            px: 3,
            "&:hover": { bgcolor: "#27272A" }
          }}
        >
          {t("actions.export")}
        </Button>
      </Paper>

      {/* TABLE */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 8 }}>
          <CircularProgress size={30} sx={{ color: "#000" }} />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3, borderColor: "divider", overflow: "hidden" }}>
          <Table>
            <TableHead sx={{ bgcolor: alpha("#000", 0.02) }}>
              <TableRow>
                <TableCell sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("actions.title")}</TableCell>
                <TableCell sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("actions.owner")}</TableCell>
                <TableCell sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("actions.priority")}</TableCell>
                <TableCell sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("actions.status")}</TableCell>
                <TableCell sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("actions.due_date")}</TableCell>
                <TableCell align="right" sx={{ fontSize: 12, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em", py: 2 }}>{t("common.actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredActions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary', fontSize: 14, borderBottom: 0 }}>
                    {t('dashboard.no_actions_found') || "No actions found."}
                  </TableCell>
                </TableRow>
              ) : (
                filteredActions.map((action) => (
                  <TableRow 
                    key={action.id} 
                    hover
                    sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: alpha("#000", 0.01) } }}
                  >
                    <TableCell sx={{ fontWeight: 600, fontSize: 14, color: "text.primary", py: 2 }}>
                      {action.title}
                    </TableCell>
                    <TableCell sx={{ fontSize: 14, color: "text.secondary", py: 2 }}>{user?.full_name || t('common.me')}</TableCell>
                    <TableCell sx={{ py: 2 }}>
                      <Chip
                        label={action.priority || 'Medium'}
                        size="small"
                        variant="outlined"
                        sx={{ 
                          height: 22, 
                          fontSize: 11, 
                          fontWeight: 700, 
                          textTransform: "uppercase",
                          borderRadius: 1.5,
                          borderColor: action.priority?.toLowerCase() === "high" ? alpha("#EF4444", 0.3) : alpha("#F59E0B", 0.3),
                          color: action.priority?.toLowerCase() === "high" ? "#EF4444" : "#F59E0B",
                          bgcolor: "transparent"
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ py: 2 }}>
                      <StatusBadge status={action.status || 'pending'} />
                    </TableCell>
                    <TableCell sx={{ fontSize: 14, color: "text.secondary", py: 2 }}>{action.due_date ? new Date(action.due_date).toLocaleDateString() : 'N/A'}</TableCell>
                    <TableCell align="right" sx={{ py: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        <IconButton
                          size="small"
                          onClick={() => handleWhatsAppReminder(user?.full_name || 'Me')}
                          title={t("common.actions")}
                          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, color: "#10B981", "&:hover": { bgcolor: alpha("#10B981", 0.05), borderColor: "#10B981" } }}
                        >
                          <WhatsAppIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                        <IconButton 
                          size="small"
                          onClick={() => handleComplete(action.id)}
                          disabled={action.status === 'completed'}
                          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, color: "#3B82F6", "&:hover": { bgcolor: alpha("#3B82F6", 0.05), borderColor: "#3B82F6" } }}
                        >
                          <CompleteIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                        <IconButton 
                          size="small"
                          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, color: "text.secondary", "&:hover": { bgcolor: alpha("#000", 0.02) } }}
                        >
                          <MoreIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </Box>
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
