function NumberField({
  label,
  value,
  onChange,
  id,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  id: string;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <input
        id={id}
        type="number"
        min="0"
        max="999"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export default NumberField;
