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
  MeetingRoom as MeetingRoomIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { roomsApi } from "../../services/rooms";

const MeetingRooms: React.FC = () => {
  const { t } = useTranslation();
  const [rooms, setRooms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRoom, setEditingRoom] = useState<any>(null);
  const [formData, setFormData] = useState({
    name: "",
    location_description: "",
    capacity: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" as "success" | "error" });

  const fetchRooms = async () => {
    try {
      setLoading(true);
      const data = await roomsApi.getRooms();
      setRooms(data);
    } catch (error) {
      console.error("Failed to fetch rooms", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRooms();
  }, []);

  const handleOpenDialog = (room?: any) => {
    if (room) {
      setEditingRoom(room);
      setFormData({
        name: room.name,
        location_description: room.location_description || "",
        capacity: room.capacity || "",
      });
    } else {
      setEditingRoom(null);
      setFormData({ name: "", location_description: "", capacity: "" });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
  };

  const handleSave = async () => {
    setSubmitting(true);
    const dataToSave = { ...formData, capacity: formData.capacity ? parseInt(formData.capacity, 10) : null };
    try {
      if (editingRoom) {
        await roomsApi.updateRoom(editingRoom.id, dataToSave);
        setSnackbar({ open: true, message: t("team.room_save_success"), severity: "success" });
      } else {
        await roomsApi.createRoom(dataToSave);
        setSnackbar({ open: true, message: t("team.room_save_success"), severity: "success" });
      }
      handleCloseDialog();
      fetchRooms();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || t("common.operation_failed");
      setSnackbar({ open: true, message: errorMsg, severity: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (window.confirm(t("team.room_delete_confirm"))) {
      try {
        await roomsApi.deleteRoom(id);
        setSnackbar({ open: true, message: t("team.room_delete_success"), severity: "success" });
        fetchRooms();
      } catch (error) {
        setSnackbar({ open: true, message: t("common.delete_failed"), severity: "error" });
      }
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          {t("team.add_room")}
        </Button>
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
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.room_name")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.room_location")}</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>{t("team.room_capacity")}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t("team.actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rooms.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 5 }}>
                    <Typography color="text.secondary">
                      {t("team.no_rooms")}
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                rooms.map((room) => (
                  <TableRow key={room.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <MeetingRoomIcon color="action" />
                        <Typography fontWeight="500">{room.name}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{room.location_description || "-"}</TableCell>
                    <TableCell>{room.capacity || "-"}</TableCell>
                    <TableCell align="right">
                      <IconButton onClick={() => handleOpenDialog(room)} color="primary" size="small">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton onClick={() => handleDelete(room.id)} color="error" size="small">
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
          {editingRoom ? t("team.edit_room") : t("team.add_room")}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label={t("team.room_name")}
              fullWidth
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
            <TextField
              label={t("team.room_location")}
              fullWidth
              value={formData.location_description}
              onChange={(e) => setFormData({ ...formData, location_description: e.target.value })}
            />
            <TextField
              label={t("team.room_capacity")}
              fullWidth
              type="number"
              value={formData.capacity}
              onChange={(e) => setFormData({ ...formData, capacity: e.target.value })}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button 
            onClick={handleSave} 
            variant="contained" 
            disabled={submitting || !formData.name}
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

export default MeetingRooms;
