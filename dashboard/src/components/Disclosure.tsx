// Disclosure — accessible collapsible panel using render-prop pattern.
// Renders a button that toggles visibility of its associated panel, with
// full ARIA support and smooth height animation.
import { memo, useId, useState } from "react";

interface DisclosureProps {
  children: (api: {
    isOpen: boolean;
    setOpen: (v: boolean) => void;
    buttonId: string;
    panelId: string;
  }) => React.ReactNode;
  defaultOpen?: boolean;
}

export const Disclosure = memo(function Disclosure({
  children,
  defaultOpen = false,
}: DisclosureProps) {
  const [isOpen, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const buttonId = `${panelId}-btn`;
  return <>{children({ isOpen, setOpen, buttonId, panelId })}</>;
});
