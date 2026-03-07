import React from "react";
import { List, ListItem, ListItemText, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

interface Meeting {
  id: number;
  title: string;
  dateTime: string;
}

interface MeetingListProps {
  meetings: Meeting[];
}

const MeetingList: React.FC<MeetingListProps> = ({ meetings }) => {
  const { t } = useTranslation();

  return (
    <div>
      <Typography variant="h6">{t("upcomingMeetings")}</Typography>
      <List>
        {meetings.map((meeting) => (
          <ListItem key={meeting.id}>
            <ListItemText
              primary={meeting.title}
              secondary={new Date(meeting.dateTime).toLocaleString()}
            />
          </ListItem>
        ))}
      </List>
    </div>
  );
};

export default MeetingList;
