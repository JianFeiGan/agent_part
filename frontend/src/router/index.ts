import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/components/Layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: {
          title: '仪表盘',
          icon: 'Odometer'
        }
      },
      {
        path: 'products',
        name: 'Products',
        component: () => import('@/views/products/index.vue'),
        meta: {
          title: '商品管理',
          icon: 'Goods'
        }
      },
      {
        path: 'products/create',
        name: 'ProductCreate',
        component: () => import('@/views/products/Create.vue'),
        meta: {
          title: '创建商品',
          hidden: true
        }
      },
      {
        path: 'products/:id/edit',
        name: 'ProductEdit',
        component: () => import('@/views/products/Edit.vue'),
        meta: {
          title: '编辑商品',
          hidden: true
        }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/tasks/index.vue'),
        meta: {
          title: '任务管理',
          icon: 'List'
        }
      },
      {
        path: 'tasks/create',
        name: 'TaskCreate',
        component: () => import('@/views/tasks/Create.vue'),
        meta: {
          title: '创建任务',
          hidden: true
        }
      },
      {
        path: 'tasks/:id',
        name: 'TaskDetail',
        component: () => import('@/views/tasks/Detail.vue'),
        meta: {
          title: '任务详情',
          hidden: true
        }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/index.vue'),
        meta: {
          title: '知识库管理',
          icon: 'Collection'
        }
      },
      {
        path: 'knowledge/search',
        name: 'KnowledgeSearch',
        component: () => import('@/views/knowledge/Search.vue'),
        meta: {
          title: '检索测试',
          hidden: true
        }
      },
      // 刊登工具
      {
        path: 'listing/import',
        name: 'ListingProductImport',
        component: () => import('@/views/listing/ProductImport.vue'),
        meta: {
          title: '商品导入',
          icon: 'Upload'
        }
      },
      {
        path: 'listing/tasks',
        name: 'ListingTaskList',
        component: () => import('@/views/listing/TaskList.vue'),
        meta: {
          title: '刊登任务',
          icon: 'Promotion'
        }
      },
      {
        path: 'listing/tasks/:id',
        name: 'ListingTaskDetail',
        component: () => import('@/views/listing/TaskDetail.vue'),
        meta: {
          title: '任务详情',
          hidden: true
        }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 - 设置页面标题
router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - 商品视觉生成器`
  }
  next()
})

export default router