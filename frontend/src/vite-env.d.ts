/// <reference types="vite/client" />

declare module 'virtual:runtime-app' {
  import type { ComponentType } from 'react';
  const RuntimeApp: ComponentType;
  export default RuntimeApp;
}
