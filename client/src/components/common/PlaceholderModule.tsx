/**
 * Placeholder for modules not yet implemented.
 * Will be replaced in their respective phases.
 */

import { ListPane } from '../layout/ListPane';
import { DetailPane } from '../layout/DetailPane';
import { tokens } from '../../styles/tokens';

interface PlaceholderModuleProps {
  name: string;
  phase: string;
}

export function PlaceholderModule({ name, phase }: PlaceholderModuleProps) {
  return (
    <>
      <ListPane title={name}>
        <div style={styles.placeholder}>
          <p style={styles.text}>Coming in {phase}</p>
        </div>
      </ListPane>
      <DetailPane>
        <div style={styles.detailPlaceholder}>
          <h2 style={styles.heading}>{name}</h2>
          <p style={styles.text}>This module will be implemented in {phase}.</p>
        </div>
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  placeholder: {
    padding: 16,
    textAlign: 'center' as const,
  },
  detailPlaceholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: 8,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 18,
    color: tokens.colors.text,
  },
  text: {
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
  },
};
