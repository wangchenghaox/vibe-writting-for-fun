import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/register', component: () => import('../views/Register.vue') },
  { path: '/novels', component: () => import('../views/NovelList.vue'), meta: { requiresAuth: true } },
  { path: '/novels/:id', component: () => import('../views/NovelDetail.vue'), meta: { requiresAuth: true } },
  { path: '/novels/:id/chat', component: () => import('../views/Chat.vue'), meta: { requiresAuth: true } },
  { path: '/', redirect: '/novels' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
