// Shared breadcrumb navigation component.
import { NavLink } from "react-router-dom";

function Breadcrumb({ items }: { items: Array<{ label: string; to?: string }> }) {
  return (
    <nav aria-label="Breadcrumb" className="breadcrumb">
      {items.map((item, i) => (
        <span key={i} className="breadcrumb-item">
          {i > 0 && (
            <span className="breadcrumb-sep" aria-hidden="true">
              /
            </span>
          )}
          {item.to ? <NavLink to={item.to}>{item.label}</NavLink> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export default Breadcrumb;
