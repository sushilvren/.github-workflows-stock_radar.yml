import tushare as ts
import pandas as pd
import requests
import json
import datetime

# ================= 1. 配置区（已锁定您的私有信息） =================
MY_TOKEN = 'uErxiYZlfergcQEFYhAjPEGZCloqCRPKFpLGElZEVaPAMVdubyXaqjEhMttrXeaj'
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/7a6e635a-8c99-4ca7-be1a-f9670b6f3621"

# 自动获取北京时间日期（GitHub服务器默认是UTC时间，需+8小时）
bj_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
TARGET_DATE = bj_time.strftime('%Y%m%d')

# 初始化商家定制接口（指向私有节点 121.40.135.59）
pro = ts.pro_api(MY_TOKEN)
pro._DataApi__http_url = "http://121.40.135.59:8010/"

def get_market_data():
    # 核心监控名单：包含万马股份、舒华体育等 10 只标的
    stocks = [
        '002276.SZ', '605299.SH', '002255.SZ', '301488.SZ', '300936.SZ', 
        '300051.SZ', '600376.SH', '600604.SH', '000677.SZ', '000509.SZ'
    ]
    
    try:
        # 1. 抓取行情数据
        df = pro.daily(ts_code=','.join(stocks), trade_date=TARGET_DATE)
        # 2. 抓取基本面指标（量比、换手率）
        df_basic = pro.daily_basic(ts_code=','.join(stocks), trade_date=TARGET_DATE)

        if df is None or df.empty:
            return f"📢 提醒：{TARGET_DATE} 暂无开盘数据。如果是周一早盘，请在 09:26 后再次运行。"

        # 3. 暴力对齐逻辑：防止商家节点因索引问题报错
        # 将 basic 数据转为字典方便快速匹配
        basic_dict = df_basic.set_index('ts_code').to_dict('index') if 'ts_code' in df_basic.columns else df_basic.to_dict('index')

        results = []
        for idx, row in df.iterrows():
            # 兼容处理：代码可能在列里，也可能在索引里
            code = row['ts_code'] if 'ts_code' in row else idx
            b_info = basic_dict.get(code, {})
            
            # 提取核心指标（若缺失则给默认值防止报错）
            v_ratio = float(b_info.get('volume_ratio', 1.0) or 1.0)
            p_chg = float(row.get('pct_chg', 0) or 0)
            t_rate = float(b_info.get('turnover_rate', 0) or 0)
            
            # 🔥 战斗力核心算法：量比(50%) + 涨幅(30%) + 换手(20%)
            score = v_ratio * 50 + p_chg * 30 + (1.0 if t_rate == 0 else t_rate) * 20
            
            results.append({
                'code': code, 
                'close': row['close'], 
                'score': score, 
                'v_ratio': v_ratio
            })
        
        # 按战斗力评分从高到低排序，取前 5 名
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:5]

    except Exception as e:
        return f"❌ 脚本运行异常: {e}"

def push_to_feishu(content):
    """
    将结果推送到飞书机器人
    """
    if isinstance(content, str):
        msg = content
    else:
        msg = f"🚀 **{TARGET_DATE} 黑马战斗力排位 (云端自动版)**\n"
        msg += "----------------------------------\n"
        for i, item in enumerate(content):
            # 根据得分生成星级 (最高5星)
            stars = "⭐" * min(5, max(1, int(item['score'] / 20)))
            msg += f"**TOP {i+1}: {item['code']}**\n"
            msg += f"价格: **{item['close']:.2f}** | 战力: {stars}\n"
            msg += f"信号: {'🔥 主力爆量' if item['v_ratio'] > 2.5 else '📈 趋势持平'}\n"
            msg += "------------------\n"
        msg += "💡 提示：请对照同花顺买入区间操作。"
    
    # 发送 POST 请求给飞书 Webhook
    payload = {"msg_type": "text", "content": {"text": msg}}
    try:
        requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        print("✅ 消息已成功推送到飞书！")
    except Exception as e:
        print(f"❌ 飞书推送失败: {e}")

if __name__ == "__main__":
    # 执行流程
    final_data = get_market_data()
    push_to_feishu(final_data)
