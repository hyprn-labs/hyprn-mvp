import type { ReactNode } from 'react';
import { Button } from './components';

/** One control row per table. The caller owns paging, reads and column selection. */
export function TableControls({
  label,
  itemLabel,
  page,
  pageSize,
  total,
  onPage,
  columns,
}: {
  label: string;
  itemLabel: string;
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  columns?: ReactNode;
}) {
  const pages = Math.ceil(total / pageSize);
  return (
    <div className="hf-table-controls">
      {columns}
      <nav className="hf-pagination" aria-label={label}>
        <span>
          {itemLabel} {total ? page * pageSize + 1 : 0}–{Math.min((page + 1) * pageSize, total)} of{' '}
          {total}
        </span>
        {pages > 1 && (
          <>
            <Button disabled={page === 0} onClick={() => onPage(page - 1)}>
              Previous
            </Button>
            <Button disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>
              Next
            </Button>
          </>
        )}
      </nav>
    </div>
  );
}
