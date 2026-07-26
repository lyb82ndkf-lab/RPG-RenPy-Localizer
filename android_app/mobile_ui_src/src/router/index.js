import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/library'
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('../views/LibraryView.vue')
    },
    {
      path: '/translations',
      name: 'translations',
      component: () => import('../views/TranslationsView.vue')
    },
    {
      path: '/data',
      name: 'data',
      component: () => import('../views/CheatsView.vue')
    },
    {
      path: '/saves',
      name: 'saves',
      component: () => import('../views/SavesView.vue')
    },
    {
      path: '/maps',
      name: 'maps',
      component: () => import('../views/MapsView.vue')
    },
    {
      path: '/cheats',
      name: 'cheats',
      component: () => import('../views/CheatsView.vue')
    },
    {
      path: '/controls',
      name: 'controls',
      component: () => import('../views/ControlsView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue')
    }
  ]
})

export default router
