import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Snackbar,
  Alert,
  CircularProgress,
  Paper,
  Chip,
  MenuItem
} from "@mui/material";
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Person as PersonIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { teamApi } from "../../services/team";

const TeamMembers: React.FC = () => {
  const { t } = useTranslation();
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingMember, setEditingMember] = useState<any>(null);
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone_number: "",
    position: "",
    department: "",
    role: "participant",
  });
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" as "success" | "error" });

  const fetchMembers = async () => {
    try {
      setLoading(true);
      const data = await teamApi.getTeamMembers();
      setMembers(data);
    } catch (error) {
      console.error("Failed to fetch team members", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMembers();

    // Auto-refresh team members every 30 seconds to catch status changes
    // (e.g., when user activates their account after invitation)
    const refreshInterval = setInterval(() => {
      fetchMembers();
    }, 30000); // 30 seconds

    return () => clearInterval(refreshInterval);
  }, []);

  const handleOpenDialog = (member?: any) => {
    if (member) {
      setEditingMember(member);
      setFormData({
        full_name: member.full_name,
        email: member.email,
        phone_number: member.phone_number || "",
        position: member.position || "",
        department: member.department || "",
        role: member.role || "participant",
      });
    } else {
      setEditingMember(null);
      setFormData({
        full_name: "",
        email: "",
        phone_number: "",
        position: "",
        department: "",
        role: "participant",
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
  };

  const handleSave = async () => {
    setSubmitting(true);
    try {
      if (editingMember) {
        await teamApi.updateTeamMember(editingMember.id, formData);
      } else {
        await teamApi.createTeamMember(formData);
      }
      setSnackbar({ open: true, message: t("team.save_success"), severity: "success" });
      handleCloseDialog();
      fetchMembers();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || "Operation failed";
      setSnackbar({ open: true, message: errorMsg, severity: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (window.confirm(t("team.delete_confirm"))) {
      try {
        await teamApi.deleteTeamMember(id);
        setSnackbar({ open: true, message: t("team.delete_success"), severity: "success" });
        fetchMembers();
      } catch (error) {
        setSnackbar({ open: true, message: "Delete failed", severity: "error" });
      }
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">{t('team.members_list')}</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<RefreshIcon />}
            onClick={() => fetchMembers()}
            disabled={loading}
          >
            {t("common.refresh") || "Refresh"}
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            {t("team.add_member")}
          </Button>
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 10 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead sx={{ bgcolor: "action.hover" }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.full_name")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.email")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.role")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.position")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.department")}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t("team.actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <PersonIcon color="action" />
                      <Typography>{member.full_name}</Typography>
                      {member.status === "PENDING" && (
                        <Chip label="Invitation Sent" size="small" color="warning" variant="outlined" />
                      )}
                      {member.status === "ACTIVE" && (
                        <Chip label="User" size="small" color="success" variant="outlined" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>{member.email}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                      {t(`team.role_${member.role}`) || member.role}
                    </Typography>
                  </TableCell>
                  <TableCell>{member.source === "user" ? "Registered User" : (member.position || "-")}</TableCell>
                  <TableCell>{member.department || "-"}</TableCell>
                  <TableCell align="right">
                    <IconButton onClick={() => handleOpenDialog(member)} color="primary" size="small">
                      <EditIcon />
                    </IconButton>
                    <IconButton onClick={() => handleDelete(member.id)} color="error" size="small">
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingMember ? t("team.edit_member") : t("team.add_member")}</DialogTitle>
        <DialogContent dividers>
          <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField label={t("team.full_name")} border="none" fullWidth value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
            <TextField label={t("team.email")} fullWidth type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
            
            <TextField
              select
              label={t("team.role")}
              fullWidth
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            >
              <MenuItem value="participant">{t("team.role_participant")}</MenuItem>
              <MenuItem value="manager">{t("team.role_manager")}</MenuItem>
              <MenuItem value="admin">{t("team.role_admin")}</MenuItem>
            </TextField>

            <TextField label={t("team.phone")} fullWidth value={formData.phone_number} onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })} />
            <TextField label={t("team.position")} fullWidth value={formData.position} onChange={(e) => setFormData({ ...formData, position: e.target.value })} />
            <TextField label={t("team.department")} fullWidth value={formData.department} onChange={(e) => setFormData({ ...formData, department: e.target.value })} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button onClick={handleSave} variant="contained" disabled={submitting}>{submitting ? <CircularProgress size={24} /> : t("common.save")}</Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar({...snackbar, open: false})}>
        <Alert onClose={() => setSnackbar({...snackbar, open: false})} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TeamMembers;
