<template>
  <div class="product-import">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>导入商品</span>
        </div>
      </template>

      <el-form
        :model="form"
        :rules="rules"
        ref="formRef"
        label-width="120px"
        style="max-width: 600px"
      >
        <el-form-item label="SKU" prop="sku">
          <el-input v-model="form.sku" placeholder="请输入商品SKU" />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入商品标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入商品描述"
          />
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="form.category" placeholder="请输入商品类目" />
        </el-form-item>
        <el-form-item label="品牌">
          <el-input v-model="form.brand" placeholder="请输入品牌名称" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">
            导入商品
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="importedProduct" style="margin-top: 20px">
      <template #header>
        <span>导入结果</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="SKU">{{ importedProduct.sku }}</el-descriptions-item>
        <el-descriptions-item label="标题">{{ importedProduct.title }}</el-descriptions-item>
        <el-descriptions-item label="类目">{{ importedProduct.category || '-' }}</el-descriptions-item>
        <el-descriptions-item label="品牌">{{ importedProduct.brand || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ importedProduct.description || '-' }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 16px">
        <el-button type="primary" @click="$router.push({ name: 'ListingTaskList' })">
          创建刊登任务
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { importProduct } from '@/api/listing'
import type { ProductImportRequest, ProductResponse } from '@/types/listing'

const formRef = ref<FormInstance>()
const loading = ref(false)
const importedProduct = ref<ProductResponse | null>(null)

const form = reactive<ProductImportRequest>({
  sku: '',
  title: '',
  description: '',
  category: '',
  brand: '',
})

const rules: FormRules = {
  sku: [{ required: true, message: '请输入SKU', trigger: 'blur' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await importProduct(form)
    if (res.data.code === 200) {
      importedProduct.value = res.data.data
      ElMessage.success('商品导入成功')
    } else {
      ElMessage.error(res.data.message || '导入失败')
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '导入失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  formRef.value?.resetFields()
  importedProduct.value = null
}
</script>
