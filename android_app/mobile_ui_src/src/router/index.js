import { createRouter, createWebHashHistory } from 'vue-router'
import LibraryView from '../views/LibraryView.vue'
import TranslationsView from '../views/TranslationsView.vue'
import CheatsView from '../views/CheatsView.vue'
import SettingsView from '../views/SettingsView.vue'

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
      component: LibraryView
    },
    {
      path: '/translations',
      name: 'translations',
      component: TranslationsView
    },
    {
      path: '/cheats',
      name: 'cheats',
      component: CheatsView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    }
  ]
})

export default router
