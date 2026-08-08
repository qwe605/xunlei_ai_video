import { createRoot } from 'react-dom/client'
import 'plyr/dist/plyr.css'
import './styles/global.css'
import { App } from './app/App'

// Plyr 会命令式接管 video DOM；开发模式下 StrictMode 的双初始化会让第二次
// 生命周期持有已销毁的媒体节点，因此入口只保留 React 的单次挂载。
createRoot(document.getElementById('root')!).render(<App />)
