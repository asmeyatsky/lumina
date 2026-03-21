import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, Search, ChevronLeft, ChevronRight } from "lucide-react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  pageSize?: number;
  searchable?: boolean;
  searchPlaceholder?: string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  className?: string;
}

type SortDirection = "asc" | "desc" | null;

export default function DataTable<T extends Record<string, any>>({
  columns,
  data,
  pageSize = 10,
  searchable = false,
  searchPlaceholder = "Search...",
  onRowClick,
  emptyMessage = "No data available",
  className = "",
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const filteredData = useMemo(() => {
    if (!search.trim()) return data;
    const term = search.toLowerCase();
    return data.filter((row) =>
      columns.some((col) => {
        const val = row[col.key];
        return val != null && String(val).toLowerCase().includes(term);
      })
    );
  }, [data, search, columns]);

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDir) return filteredData;
    return [...filteredData].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const cmp =
        typeof aVal === "number" && typeof bVal === "number"
          ? aVal - bVal
          : String(aVal).localeCompare(String(bVal));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filteredData, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedData.length / pageSize));
  const pagedData = sortedData.slice(page * pageSize, (page + 1) * pageSize);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === "asc") setSortDir("desc");
      else if (sortDir === "desc") {
        setSortKey(null);
        setSortDir(null);
      }
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  };

  const SortIcon = ({ colKey }: { colKey: string }) => {
    if (sortKey !== colKey) return <ChevronsUpDown size={14} className="text-gray-600" />;
    if (sortDir === "asc") return <ChevronUp size={14} className="text-accent" />;
    return <ChevronDown size={14} className="text-accent" />;
  };

  return (
    <div className={`${className}`}>
      {searchable && (
        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder={searchPlaceholder}
            className="input-field pl-9"
          />
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wider ${
                    col.sortable !== false ? "cursor-pointer select-none hover:text-gray-300" : ""
                  }`}
                  style={col.width ? { width: col.width } : undefined}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                >
                  <div className="flex items-center gap-1.5">
                    {col.header}
                    {col.sortable !== false && <SortIcon colKey={col.key} />}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="text-center py-12 text-gray-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              pagedData.map((row, i) => (
                <tr
                  key={i}
                  className={`border-b border-white/[0.04] last:border-0 ${
                    onRowClick
                      ? "cursor-pointer hover:bg-white/[0.02] transition-colors"
                      : ""
                  }`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="py-3 px-4 text-gray-300">
                      {col.render ? col.render(row) : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.04]">
          <span className="text-xs text-gray-500">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, sortedData.length)} of{" "}
            {sortedData.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="p-1.5 rounded hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={16} className="text-gray-400" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i;
              } else if (page < 3) {
                pageNum = i;
              } else if (page > totalPages - 4) {
                pageNum = totalPages - 5 + i;
              } else {
                pageNum = page - 2 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-8 h-8 rounded text-xs font-medium transition-colors ${
                    page === pageNum
                      ? "bg-accent/20 text-accent"
                      : "text-gray-400 hover:bg-white/[0.06]"
                  }`}
                >
                  {pageNum + 1}
                </button>
              );
            })}
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="p-1.5 rounded hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={16} className="text-gray-400" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
