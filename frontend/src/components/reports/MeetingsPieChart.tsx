import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useTranslation } from "react-i18next";
import { useTheme } from "@mui/material";

interface Props {
  data: {
    completed: number;
    scheduled: number;
    cancelled: number;
  };
}

const COLORS = ["#4caf50", "#2196f3", "#f44336"];

const MeetingsPieChart: React.FC<Props> = ({ data }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const chartData = [
    { name: t("common.completed"), value: data.completed },
    { name: t("common.scheduled"), value: data.scheduled },
    { name: t("common.cancelled"), value: data.cancelled },
  ];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart margin={{ top: 0, right: 0, bottom: 20, left: 0 }}>
        <Pie
          data={chartData}
          cx="50%"
          cy="45%"
          labelLine={true}
          label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend
          verticalAlign="bottom"
          height={36}
          wrapperStyle={{ paddingTop: "20px" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default MeetingsPieChart;
