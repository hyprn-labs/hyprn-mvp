import { createRoot } from 'react-dom/client';
import { Workspace } from './Workspace';
import { initializeUsersnap } from './usersnap';
import './design/tokens.css';
import './design/foundry.css';
import './styles.css';
createRoot(document.getElementById('root')!).render(<Workspace />);
initializeUsersnap();
