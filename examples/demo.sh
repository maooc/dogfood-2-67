#!/bin/bash
# envsync 演示脚本

echo "=== envsync 演示 ==="

echo ""
echo "1. 创建开发环境"
envsync env:create development

echo ""
echo "2. 创建生产环境"
envsync env:create production

echo ""
echo "3. 列出所有环境"
envsync env:list

echo ""
echo "4. 在开发环境中设置变量"
envsync env:set development DEBUG true
envsync env:set development DATABASE_URL "postgresql://user:pass@localhost:5432/devdb"
envsync env:set development API_KEY "dev-secret-123" --sensitive
envsync env:set development PORT 8000

echo ""
echo "5. 在生产环境中设置变量"
envsync env:set production DEBUG false
envsync env:set production DATABASE_URL "postgresql://user:pass@prod-db:5432/proddb"
envsync env:set production API_KEY "prod-secret-456" --sensitive
envsync env:set production PORT 80

echo ""
echo "6. 查看开发环境配置"
envsync env:show development

echo ""
echo "7. 对比开发和生产环境的差异"
envsync diff development production

echo ""
echo "8. 验证环境配置"
envsync validate development
envsync validate production

echo ""
echo "9. 创建快照"
envsync snapshot:create "before-change" --description "初始配置快照"

echo ""
echo "10. 列出快照"
envsync snapshot:list

echo ""
echo "11. 导出环境配置"
echo "导出为 .env 格式:"
envsync export development --format env
echo ""
echo "导出为 JSON 格式:"
envsync export production --format json

echo ""
echo "=== 演示完成 ==="
