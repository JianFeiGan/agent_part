<template>
  <div class="product-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商品列表</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            创建商品
          </el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="queryParams" class="search-form">
        <el-form-item label="商品名称">
          <el-input
            v-model="queryParams.name"
            placeholder="请输入商品名称"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="queryParams.category" placeholder="请选择分类" clearable>
            <el-option
              v-for="(label, value) in ProductCategoryLabels"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 商品表格 -->
      <el-table
        v-loading="loading"
        :data="productList"
        style="width: 100%"
      >
        <el-table-column prop="product_id" label="商品ID" width="180" />
        <el-table-column prop="name" label="商品名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            {{ ProductCategoryLabels[row.category] || row.category }}
          </template>
        </el-table-column>
        <el-table-column prop="brand" label="品牌" width="120" show-overflow-tooltip />
        <el-table-column prop="selling_points" label="卖点数量" width="100">
          <template #default="{ row }">
            {{ row.selling_points?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="tag in (row.tags || []).slice(0, 3)"
              :key="tag"
              size="small"
              style="margin-right: 4px;"
            >
              {{ tag }}
            </el-tag>
            <span v-if="(row.tags || []).length > 3">+{{ row.tags.length - 3 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button type="success" link @click="handleCreateTask(row)">
              生成任务
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ProductCategoryLabels } from '@/types/product'
import type { Product, ProductQueryParams } from '@/types/product'
import { getProducts, deleteProduct } from '@/api/products'

/**
 * 商品列表页面
 * @description 商品管理列表，支持搜索、分页、编辑、删除等操作
 */

const router = useRouter()

// 加载状态
const loading = ref(false)

// 商品列表
const productList = ref<Product[]>([])

// 总数
const total = ref(0)

// 查询参数
const queryParams = reactive<ProductQueryParams>({
  name: '',
  category: undefined,
  page: 1,
  page_size: 10
})

// 加载商品列表
const loadProducts = async () => {
  loading.value = true
  try {
    const response = await getProducts(queryParams)
    if (response.data.code === 200) {
      productList.value = response.data.data.items
      total.value = response.data.data.total
    } else {
      ElMessage.error(response.data.message || '加载商品列表失败')
    }
  } catch (error) {
    console.error('加载商品列表失败:', error)
    ElMessage.error('加载商品列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  queryParams.page = 1
  loadProducts()
}

// 重置
const handleReset = () => {
  queryParams.name = ''
  queryParams.category = undefined
  queryParams.page = 1
  loadProducts()
}

// 创建商品
const handleCreate = () => {
  router.push('/products/create')
}

// 编辑商品
const handleEdit = (row: Product) => {
  router.push(`/products/${row.product_id}/edit`)
}

// 创建任务
const handleCreateTask = (row: Product) => {
  router.push({
    path: '/tasks/create',
    query: { product_id: row.product_id }
  })
}

// 删除商品
const handleDelete = async (row: Product) => {
  try {
    await ElMessageBox.confirm(`确定要删除商品 "${row.name}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const response = await deleteProduct(row.product_id)
    if (response.data.code === 200) {
      ElMessage.success('删除成功')
      loadProducts()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch {
    // 用户取消
  }
}

// 分页大小变化
const handleSizeChange = (size: number) => {
  queryParams.page_size = size
  loadProducts()
}

// 页码变化
const handleCurrentChange = (page: number) => {
  queryParams.page = page
  loadProducts()
}

onMounted(() => {
  loadProducts()
})
</script>

<style scoped>
.product-list {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>