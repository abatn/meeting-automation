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
    <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            <TableCell>
              <TableSortLabel
                active={orderBy === "name"}
                direction={orderBy === "name" ? order : "asc"}
                onClick={() => handleRequestSort("name")}
              >
                {t("common.name")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center">
              <TableSortLabel
                active={orderBy === "completed"}
                direction={orderBy === "completed" ? order : "asc"}
                onClick={() => handleRequestSort("completed")}
              >
                {t("common.completed")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center">
              <TableSortLabel
                active={orderBy === "pending"}
                direction={orderBy === "pending" ? order : "asc"}
                onClick={() => handleRequestSort("pending")}
              >
                {t("common.pending")}
              </TableSortLabel>
            </TableCell>
            <TableCell align="center">
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
            <TableRow key={row.user_id}>
              <TableCell component="th" scope="row">
                {row.name}
              </TableCell>
              <TableCell align="center">{row.completed}</TableCell>
              <TableCell align="center">{row.pending}</TableCell>
              <TableCell align="center">{row.overdue}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ProductivityTable;
