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
} from "@mui/material";
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Person as PersonIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { teamApi } from "../../services/team";

const TeamManagement: React.FC = () => {
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
      });
    } else {
      setEditingMember(null);
      setFormData({
        full_name: "",
        email: "",
        phone_number: "",
        position: "",
        department: "",
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
        setSnackbar({ open: true, message: t("team.save_success"), severity: "success" });
      } else {
        await teamApi.createTeamMember(formData);
        setSnackbar({ open: true, message: t("team.save_success"), severity: "success" });
      }
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
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold">
            {t("team.title")}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {t("team.subtitle")}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          {t("team.add_member")}
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 10 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} elevation={2}>
          <Table>
            <TableHead sx={{ bgcolor: "action.hover" }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.full_name")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.email")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.position")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.department")}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t("team.actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {members.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 5 }}>
                    <Typography color="text.secondary">
                      {t("team.no_members")}
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                members.map((member) => (
                  <TableRow key={member.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <PersonIcon color="action" />
                        <Typography fontWeight="500">{member.full_name}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{member.email}</TableCell>
                    <TableCell>{member.position || "-"}</TableCell>
                    <TableCell>{member.department || "-"}</TableCell>
                    <TableCell align="right">
                      <IconButton onClick={() => handleOpenDialog(member)} color="primary" size="small">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton onClick={() => handleDelete(member.id)} color="error" size="small">
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingMember ? t("team.edit_member") : t("team.add_member")}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label={t("team.full_name")}
              fullWidth
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            />
            <TextField
              label={t("team.email")}
              fullWidth
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
            <TextField
              label={t("team.phone")}
              fullWidth
              value={formData.phone_number}
              onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
              placeholder="+216 ..."
            />
            <TextField
              label={t("team.position")}
              fullWidth
              value={formData.position}
              onChange={(e) => setFormData({ ...formData, position: e.target.value })}
            />
            <TextField
              label={t("team.department")}
              fullWidth
              value={formData.department}
              onChange={(e) => setFormData({ ...formData, department: e.target.value })}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button 
            onClick={handleSave} 
            variant="contained" 
            disabled={submitting || !formData.full_name || !formData.email}
          >
            {submitting ? <CircularProgress size={24} /> : t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar 
        open={snackbar.open} 
        autoHideDuration={4000} 
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TeamManagement;
