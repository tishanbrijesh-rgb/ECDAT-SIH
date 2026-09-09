function Select({
  label,
  value,
  options,
  onChange,
  id,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option value={o} key={o}>
            {o[0].toUpperCase() + o.slice(1)}
          </option>
        ))}
      </select>
    </label>
  );
}

export default Select;
