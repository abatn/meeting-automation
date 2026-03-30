import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Box,
  alpha,
  Paper
} from "@mui/material";
import { useTranslation } from "react-i18next";

interface ProductivityData {
  user_id: number;
  name: string;
  completed: number;
  pending: number;
  overdue: number;
}

interface Props {
  data: ProductivityData[];
}

const ProductivityTable: React.FC<Props> = ({ data }) => {
  const { t } = useTranslation();
  const [order, setOrder] = React.useState<"asc" | "desc">("desc");
  const [orderBy, setOrderBy] =
    React.useState<keyof ProductivityData>("completed");

  const handleRequestSort = (property: keyof ProductivityData) => {
    const isAsc = orderBy === property && order === "asc";
    setOrder(isAsc ? "desc" : "asc");
    setOrderBy(property);
  };

  const sortedData = [...data].sort((a, b) => {
    if (a[orderBy] < b[orderBy]) {
      return order === "asc" ? -1 : 1;
    }
    if (a[orderBy] > b[orderBy]) {
      return order === "asc" ? 1 : -1;
    }
    return 0;
  });

  const headerCellStyle = {
    fontSize: 12,
    fontWeight: 600,
    color: "text.secondary",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    py: 1.5,
    borderBottom: "1px solid",
    borderColor: "divider"
  };

  return (
    <TableContainer 
      component={Paper} 
      elevation={0}
      sx={{ 
        maxHeight: 600, 
        overflowX: "auto", 
        width: "100%",
        borderRadius: "12px",
        border: "1px solid",
        borderColor: "divider",
        "&::-webkit-scrollbar": {
          height: "6px",
        },
        "&::-webkit-scrollbar-thumb": {
          backgroundColor: "rgba(0,0,0,0.1)",
          borderRadius: "3px",
        },
      }}
    >
      <Table stickyHeader size="small" sx={{ minWidth: 800 }}>
        <TableHead>
          <TableRow>
            <TableCell sx={headerCellStyle}>
              <TableSortLabel
                active={orderBy === "name"}
                direction={orderBy === "name" ? order : "asc"}
                onClick={() => handleRequestSort("name")}
              >
                {t("common.name")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center" sx={headerCellStyle}>
              <TableSortLabel
                active={orderBy === "completed"}
                direction={orderBy === "completed" ? order : "asc"}
                onClick={() => handleRequestSort("completed")}
              >
                {t("common.completed")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center" sx={headerCellStyle}>
              <TableSortLabel
                active={orderBy === "pending"}
                direction={orderBy === "pending" ? order : "asc"}
                onClick={() => handleRequestSort("pending")}
              >
                {t("common.pending")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center" sx={headerCellStyle}>
              <TableSortLabel
                active={orderBy === "overdue"}
                direction={orderBy === "overdue" ? order : "asc"}
                onClick={() => handleRequestSort("overdue")}
              >
                {t("common.overdue")}
              </TableSortLabel>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedData.map((row) => (
            <TableRow 
              key={row.user_id}
              hover
              sx={{ "&:hover": { bgcolor: alpha("#000", 0.01) }, "&:last-child td": { borderBottom: 0 } }}
            >
              <TableCell component="th" scope="row" sx={{ py: 2, fontSize: 14, fontWeight: 500 }}>
                {row.name}
              </TableCell>
              <TableCell align="center" sx={{ py: 2, fontSize: 14 }}>{row.completed}</TableCell>
              <TableCell align="center" sx={{ py: 2, fontSize: 14 }}>{row.pending}</TableCell>
              <TableCell align="center" sx={{ py: 2, fontSize: 14 }}>{row.overdue}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ProductivityTable;
