import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TableSortLabel,
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

  return (
    <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            <TableCell>
              <TableSortLabel
                active={orderBy === "name"}
                direction={orderBy === "name" ? order : "asc"}
                onClick={() => handleRequestSort("name")}
              >
                {t("Name")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">
              <TableSortLabel
                active={orderBy === "completed"}
                direction={orderBy === "completed" ? order : "asc"}
                onClick={() => handleRequestSort("completed")}
              >
                {t("Completed")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">
              <TableSortLabel
                active={orderBy === "pending"}
                direction={orderBy === "pending" ? order : "asc"}
                onClick={() => handleRequestSort("pending")}
              >
                {t("Pending")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">
              <TableSortLabel
                active={orderBy === "overdue"}
                direction={orderBy === "overdue" ? order : "asc"}
                onClick={() => handleRequestSort("overdue")}
              >
                {t("Overdue")}
              </TableSortLabel>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedData.map((row) => (
            <TableRow key={row.user_id}>
              <TableCell component="th" scope="row">
                {row.name}
              </TableCell>
              <TableCell align="right">{row.completed}</TableCell>
              <TableCell align="right">{row.pending}</TableCell>
              <TableCell align="right">{row.overdue}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ProductivityTable;
