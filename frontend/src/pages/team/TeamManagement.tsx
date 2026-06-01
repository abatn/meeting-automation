import React, { useState, ReactNode } from "react";
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
} from "@mui/material";
import {
  Person as PersonIcon,
  MeetingRoom as MeetingRoomIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import TeamMembersPage from "./TeamMembersPage"; // CORRECTED IMPORT
import MeetingRoomsPage from "./MeetingRoomsPage"; // CORRECTED IMPORT

interface TabPanelProps {
  children?: ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`team-tabpanel-${index}`}
      aria-labelledby={`team-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3, px: 3, pb: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const TeamManagement: React.FC = () => {
  const { t } = useTranslation();
  const [currentTab, setCurrentTab] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <Box>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h4" fontWeight="bold">
            {t("team.title")}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {t("team.subtitle")}
          </Typography>
        </Box>

        <Paper variant="outlined">
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs value={currentTab} onChange={handleTabChange} aria-label={t("team.tabs_aria_label")}>
                    <Tab 
                        icon={<PersonIcon />} 
                        iconPosition="start" 
                        label={t("team.members_tab")} 
                        id="team-tab-0"
                        aria-controls="team-tabpanel-0"
                    />
                    <Tab 
                        icon={<MeetingRoomIcon />} 
                        iconPosition="start" 
                        label={t("team.rooms_tab")}
                        id="team-tab-1"
                        aria-controls="team-tabpanel-1"
                    />
                </Tabs>
            </Box>
            
            <TabPanel value={currentTab} index={0}>
                <TeamMembersPage />
            </TabPanel>
            <TabPanel value={currentTab} index={1}>
                <MeetingRoomsPage />
            </TabPanel>
        </Paper>
    </Box>
  );
};

export default TeamManagement;
