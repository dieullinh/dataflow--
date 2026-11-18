"""
MINH AN TECHNOLOGY SOLUTIONS - DUAL PORTAL (BUSINESS & CUSTOMER SEPARATE VIEWS)
- Outer background: Pure clean white (#ffffff)
- Inner canvas background: Soft pastel mint (#e4f6ee / #d8f3e5)
- Separate dedicated Customer Portal view & Business CRM Studio
"""

import http.server
import socketserver
import json
import os
import urllib.parse
from datetime import datetime
from dataclasses import asdict

from agent_engine import CatalogService, MinhAnSalesAIAgent, ExtractedInquiry, OpportunityProfile
from gemini_llm import call_customer_consultant, call_gemini_parser, call_gemini_rewrite_email, call_gemini_copilot

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "data", "master_catalog.json")
INQUIRIES_PATH = os.path.join(BASE_DIR, "data", "test_inquiries.json")

user_gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
catalog_service = CatalogService(CATALOG_PATH)
agent = MinhAnSalesAIAgent(catalog_service)
crm_records = []

def generate_ai_assessment(opp: OpportunityProfile) -> str:
    if opp.approval_required:
        return (
            f"💡 [AI Đề xuất]: Mức chiết khấu {opp.discount_pct}% vượt quy chế 10%. "
            f"Giá trị đơn hàng lớn ({opp.subtotal:,.0f} VNĐ). "
            f"Đề xuất Trưởng phòng DUYỆT nếu khách thanh toán tạm ứng 50% hoặc ký hợp đồng tuần này."
        )
    else:
        return (
            f"💡 [AI Đánh giá]: Chiết khấu {opp.discount_pct}% nằm trong quyền tự quyết của NVKD. "
            f"Hồ sơ đã được xác thực mã SKU và kiểm tra tồn kho khả dụng ({opp.deadline_feasibility})."
        )

DEFAULT_SAMPLE_INQUIRIES = [
    {
        "id": "INQ-2026-001",
        "received_at": "2026-11-10T14:30:00",
        "source": "Email",
        "customer": {
            "company_name": "Công ty Cổ phần Giải pháp LogiTech",
            "contact_person": "Anh Trần Tuấn - Trưởng phòng IT",
            "email": "tuan.tran@logitech-vn.example",
            "phone": "0912345678"
        },
        "raw_content": "Chào Minh An,\nCông ty tôi đang cần trang bị hạ tầng mạng cho văn phòng chi nhánh mới tại Q7 gồm:\n- 1 máy chủ Dell R750xs cấu hình chuẩn\n- 2 chiếc Switch Cisco 24 cổng PoE mã C9200L\n- 6 bộ phát wifi Aruba AP22 treo trần\n- 1 bộ lưu điện APC 3kVA\n- Kèm dịch vụ lắp đặt triển khai trọn gói.\n\nTổng ngân sách dự trù bên tôi khoảng 200 triệu. Yêu cầu bàn giao và nghiệm thu xong trước ngày 20/11/2026. Đề xuất chiết khấu thêm 12% so với giá niêm yết.\nTuấn - IT Manager."
    },
    {
        "id": "INQ-2026-002",
        "received_at": "2026-11-11T08:15:00",
        "source": "Web Form",
        "customer": {
            "company_name": "Công ty TNHH May Mặc Hưng Phát",
            "contact_person": "Chị Mai Hương - Kế toán trưởng",
            "email": "huong.mai@hungphatgarment.example",
            "phone": "0988776655"
        },
        "raw_content": "Cần báo giá gấp 2 con Firewall Fortinet 60F và 4 con Wifi Aruba AP22. Cần hàng gấp trong 3 ngày để lắp nhà xưởng. Chiết khấu thương mại mong muốn 5%."
    }
]

def load_sample_crm_data():
    global crm_records
    crm_records.clear()
    sample_inquiries = None
    if os.path.exists(INQUIRIES_PATH):
        try:
            with open(INQUIRIES_PATH, "r", encoding="utf-8") as f:
                sample_inquiries = json.load(f)
        except Exception:
            sample_inquiries = None
    if not sample_inquiries:
        sample_inquiries = DEFAULT_SAMPLE_INQUIRIES

    for inq in sample_inquiries:
        extracted = agent.parse_inquiry_agent(inq)
        opp = agent.validate_and_price_agent(extracted)
        drafts = agent.generate_proposals_and_drafts(opp)
        
        record = {
            "opp_id": opp.opportunity_id,
            "customer_name": opp.customer_name,
            "contact_person": opp.contact_person,
            "email": opp.email,
            "phone": opp.phone,
            "raw_content": inq.get("raw_content", ""),
            "assigned_rep": f"{opp.assigned_rep_name} ({opp.assigned_rep_id})",
            "rep_email": opp.assigned_rep_email,
            "subtotal": opp.subtotal,
            "discount_pct": opp.discount_pct,
            "discount_amount": opp.discount_amount,
            "final_total": opp.final_total,
            "approval_status": "Chờ Trưởng phòng duyệt" if opp.approval_required else "Đúng thẩm quyền (<=10%)",
            "lead_time_days": opp.max_lead_time_days,
            "deadline_feasibility": opp.deadline_feasibility,
            "ai_assessment": generate_ai_assessment(opp),
            "checkbox_create_quote": False,
            "quote_doc_url": f"https://docs.google.com/document/d/minhan-{opp.opportunity_id.lower()}-official-quote/edit",
            "items": [asdict(i) for i in opp.items],
            "drafts": drafts,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        crm_records.append(record)

# Dữ liệu ban đầu rỗng để người dùng tự tiếp nhận yêu cầu hoặc bấm nạp mẫu theo ý muốn
# load_sample_crm_data()

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DataLens Studio · Nền Tảng Phân Tích Dữ Liệu Thông Minh</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {
      /* BẢNG MÀU HỒNG NỔI & PASTEL CAO CẤP */
      --hot-pink: #ff2a70;
      --hot-pink-hover: #e6004c;
      --vibrant-rose: #ff4d88;
      --bubblegum: #ff75a0;
      --pastel-pink-bg: #fff0f5;
      --pastel-pink-card: #ffffff;
      --pastel-pink-subtle: #ffe6ef;
      --pastel-pink-border: #ffccd9;
      --pastel-mint: #d1fae5;
      --pastel-mint-deep: #059669;
      --pastel-lavender: #f3e8ff;
      --pastel-lavender-deep: #7e22ce;
      --pastel-yellow: #fef08a;
      --pastel-yellow-deep: #b45309;
      
      --text-dark: #2a111e;
      --text-sub: #5c293e;
      --text-muted: #8c526d;
      
      /* CLAYMORPHISM & SOFT 3D SHADOWS (HÌNH DẬP NỔI) */
      --clay-shadow: 
        10px 14px 28px rgba(255, 77, 136, 0.12),
        -6px -6px 20px rgba(255, 255, 255, 0.95),
        inset 1px 1px 2px rgba(255, 255, 255, 0.85);
      --clay-shadow-hover: 
        14px 18px 36px rgba(255, 42, 112, 0.2),
        -8px -8px 24px rgba(255, 255, 255, 1),
        inset 2px 2px 4px rgba(255, 255, 255, 0.95);
      --clay-glow-pink: 
        0 8px 24px rgba(255, 42, 112, 0.4),
        0 0 16px rgba(255, 182, 193, 0.55);
      --clay-glow-mint: 
        0 8px 24px rgba(16, 185, 129, 0.35),
        0 0 16px rgba(167, 243, 208, 0.55);
      
      --border-radius-card: 24px;
      --border-radius-pill: 9999px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Plus Jakarta Sans', sans-serif;
      -webkit-tap-highlight-color: transparent;
    }

    body {
      background-color: #fff2f6;
      background-image: 
        radial-gradient(ellipse at 15% 15%, #ffe1ec 0%, transparent 55%),
        radial-gradient(ellipse at 85% 85%, #fce7f3 0%, transparent 60%),
        radial-gradient(ellipse at 85% 15%, #e0f2fe 0%, transparent 45%),
        radial-gradient(ellipse at 15% 85%, #ecfdf5 0%, transparent 50%),
        linear-gradient(to right, rgba(255, 105, 180, 0.08) 1.5px, transparent 1.5px),
        linear-gradient(to bottom, rgba(255, 105, 180, 0.08) 1.5px, transparent 1.5px);
      background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%, 28px 28px, 28px 28px;
      min-height: 100vh;
      color: var(--text-dark);
      padding: 18px 22px 40px 22px;
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
      overflow-x: hidden;
    }

    /* PARTICLE OVERLAY CANVAS FOR SPARKLES */
    #sparkle-canvas {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      pointer-events: none;
      z-index: 999999;
    }

    /* TOP HEADER BAR */
    .top-header-bar {
      width: 100%;
      max-width: 1420px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 18px;
      flex-wrap: wrap;
      gap: 12px;
    }

    .brand-container {
      display: flex;
      align-items: center;
      gap: 12px;
      background: #ffffff;
      padding: 8px 20px 8px 12px;
      border-radius: var(--border-radius-pill);
      box-shadow: var(--clay-shadow);
      border: 1.5px solid #ffd5e2;
    }

    .brand-icon-3d {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, #ff4d88 0%, #ff1a60 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      color: white;
      box-shadow: 0 6px 16px rgba(255, 26, 96, 0.45);
      animation: gentle-float 3s infinite ease-in-out;
      cursor: pointer;
    }

    @keyframes gentle-float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    .brand-info-col h1 {
      font-size: 16.5px;
      font-weight: 900;
      background: linear-gradient(135deg, #ff1a60 0%, #d91b5c 50%, #9333ea 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.2px;
    }

    .brand-info-col p {
      font-size: 11px;
      font-weight: 700;
      color: var(--text-muted);
    }

    .top-controls-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .action-btn-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 18px;
      border-radius: var(--border-radius-pill);
      font-size: 12.5px;
      font-weight: 800;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      border: none;
      outline: none;
    }

    .btn-sound-setting {
      background: #ffffff;
      color: #9333ea;
      border: 1.5px solid #e9d5ff;
      box-shadow: var(--clay-shadow);
    }
    .btn-sound-setting:hover {
      background: #faf5ff;
      transform: translateY(-2px);
    }

    .btn-sparkle-fx {
      background: linear-gradient(135deg, #ff75a0 0%, #ff2a70 100%);
      color: #ffffff;
      box-shadow: var(--clay-glow-pink);
    }
    .btn-sparkle-fx:hover {
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 10px 28px rgba(255, 42, 112, 0.55), 0 0 20px rgba(255, 182, 193, 0.8);
    }

    /* MAIN APP WORKSTATION (CLEAN & SLEEK WINDOW) */
    .app-window-frame {
      width: 100%;
      max-width: 1420px;
      background: #ffffff;
      border-radius: var(--border-radius-card);
      border: 2px solid #ffccd9;
      box-shadow: 0 20px 50px rgba(255, 77, 136, 0.15), 0 4px 12px rgba(0, 0, 0, 0.03);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
    }

    /* WINDOW TITLE BAR (ĐÃ BỎ 3 CHẤM ĐỎ VÀNG XANH) */
    .window-header-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 22px;
      background: linear-gradient(180deg, #fff7fa 0%, #ffedf3 100%);
      border-bottom: 1.5px solid #ffd5e2;
    }

    .window-header-title {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13.5px;
      font-weight: 800;
      color: var(--hot-pink);
    }

    .window-reset-button {
      background: #ffffff;
      border: 1.5px solid #ffd5e2;
      color: var(--text-sub);
      padding: 6px 14px;
      border-radius: var(--border-radius-pill);
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11.5px;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
      transition: all 0.25s;
    }
    .window-reset-button:hover {
      background: #fff0f5;
      color: var(--hot-pink);
      border-color: var(--hot-pink);
      transform: translateY(-1px);
    }

    /* WORKBENCH: SIDEBAR + MAIN AREA */
    .workbench-grid {
      display: flex;
      min-height: 680px;
    }

    /* SIDEBAR (HỒNG NỔI & PASTEL DẬP NỔI) */
    .workbench-sidebar {
      width: 295px;
      min-width: 295px;
      background: linear-gradient(180deg, #fff8fb 0%, #fff0f5 100%);
      border-right: 1.5px solid #ffd5e2;
      padding: 22px 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 16px;
    }

    .sidebar-step-title {
      font-size: 11.5px;
      font-weight: 900;
      letter-spacing: 1.2px;
      text-transform: uppercase;
      color: var(--hot-pink);
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    /* 4 STEPS NAVIGATION LIST */
    .steps-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .step-item-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 13px 14px;
      background: #ffffff;
      border: 1.5px solid #ffd9e4;
      border-radius: 18px;
      box-shadow: 0 4px 12px rgba(255, 105, 180, 0.06), inset 0 1px 0 #ffffff;
      cursor: pointer;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      position: relative;
      overflow: hidden;
      user-select: none;
    }

    /* ACTIVE STEP */
    .step-item-card.active {
      background: linear-gradient(135deg, #ffffff 0%, #ffeaf1 100%);
      border: 2px solid var(--hot-pink);
      box-shadow: var(--clay-glow-pink);
      transform: translateY(-2px);
    }

    /* COMPLETED STEP */
    .step-item-card.completed {
      border-color: #a7f3d0;
      background: #f0fdf4;
    }

    /* LOCKED STEP (CHƯA ĐƯỢC MỞ KHÓA) */
    .step-item-card.locked {
      background: #fafafa;
      border-color: #e5e7eb;
      opacity: 0.65;
      cursor: not-allowed;
      box-shadow: none;
    }
    .step-item-card.locked:hover {
      transform: none;
      box-shadow: none;
      border-color: #e5e7eb;
    }

    .step-left-content {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .step-icon-box {
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background: #ffe4ec;
      color: var(--hot-pink);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      box-shadow: 0 3px 8px rgba(255, 77, 136, 0.15);
      transition: transform 0.2s;
    }
    .step-item-card.active .step-icon-box {
      background: linear-gradient(135deg, #ff4d88 0%, #ff1a60 100%);
      color: white;
      transform: scale(1.08);
    }
    .step-item-card.completed .step-icon-box {
      background: #d1fae5;
      color: #059669;
    }
    .step-item-card.locked .step-icon-box {
      background: #f3f4f6;
      color: #9ca3af;
      box-shadow: none;
    }

    .step-meta-col {
      display: flex;
      flex-direction: column;
      text-align: left;
    }
    .step-title-text {
      font-size: 13px;
      font-weight: 800;
      color: var(--text-dark);
    }
    .step-item-card.locked .step-title-text {
      color: #9ca3af;
    }
    .step-desc-text {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
    }
    .step-item-card.locked .step-desc-text {
      color: #d1d5db;
    }

    .step-status-tag {
      font-size: 10.5px;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: var(--border-radius-pill);
      background: #fff0f5;
      color: var(--hot-pink);
      border: 1px solid #ffd5e2;
    }
    .step-item-card.completed .step-status-tag {
      background: #d1fae5;
      color: #059669;
      border-color: #a7f3d0;
    }
    .step-item-card.locked .step-status-tag {
      background: #f3f4f6;
      color: #9ca3af;
      border-color: #e5e7eb;
    }

    /* AI ASSISTANT CARD (TRỢ LÝ CHUYÊN NGHIỆP) */
    .ai-assistant-card {
      background: #ffffff;
      border: 1.5px solid #ffccd9;
      border-radius: 20px;
      padding: 14px;
      box-shadow: var(--clay-shadow);
      display: flex;
      flex-direction: column;
      gap: 10px;
      position: relative;
    }

    .ai-assistant-header {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ai-avatar-circle {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, #ff4d88 0%, #ff1a60 100%);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      box-shadow: 0 4px 10px rgba(255, 77, 136, 0.3);
    }
    .ai-name-title {
      font-size: 12px;
      font-weight: 800;
      color: var(--text-dark);
    }

    .ai-message-bubble {
      background: #fff5f8;
      border: 1px solid #ffccd9;
      border-radius: 14px;
      padding: 10px 12px;
      font-size: 11.5px;
      font-weight: 600;
      color: var(--text-sub);
      line-height: 1.45;
    }

    /* WORKSPACE MAIN AREA */
    .workbench-main {
      flex: 1;
      padding: 24px;
      background: #ffffff;
      overflow-y: auto;
      max-height: 800px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* BANNER CỦA BƯỚC HIỆN TẠI */
    .step-hero-card {
      background: linear-gradient(135deg, #fff4f8 0%, #ffeaf2 100%);
      border: 1.5px solid #ffd5e2;
      border-radius: 22px;
      padding: 16px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 6px 20px rgba(255, 77, 136, 0.08);
      flex-wrap: wrap;
      gap: 12px;
    }

    .step-hero-left {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .step-hero-icon {
      width: 48px;
      height: 48px;
      border-radius: 16px;
      background: linear-gradient(135deg, #ff4d88 0%, #ff1a60 100%);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      box-shadow: var(--clay-glow-pink);
    }
    .step-hero-left h2 {
      font-size: 17.5px;
      font-weight: 900;
      color: var(--text-dark);
      letter-spacing: -0.2px;
    }
    .step-hero-left p {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--text-sub);
    }

    .step-indicator-pill {
      background: #ffffff;
      border: 1.5px solid #ffccd9;
      color: var(--hot-pink);
      padding: 6px 14px;
      border-radius: var(--border-radius-pill);
      font-size: 12px;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      box-shadow: 0 3px 10px rgba(255, 77, 136, 0.08);
    }

    /* 3D EMBOSSED CARDS (HÌNH NỔI DẬP) */
    .embossed-card {
      background: #ffffff;
      border: 1.5px solid #ffccd9;
      border-radius: 22px;
      padding: 20px;
      box-shadow: var(--clay-shadow);
      position: relative;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .embossed-card:hover {
      box-shadow: var(--clay-shadow-hover);
      border-color: #ff9ebb;
    }

    /* PRESET DATASETS GRID */
    .presets-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: 10px;
    }
    @media (max-width: 900px) {
      .presets-grid { grid-template-columns: 1fr; }
    }

    .preset-item-card {
      background: #fffafc;
      border: 1.5px solid #ffccd9;
      border-radius: 18px;
      padding: 16px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      position: relative;
      text-align: left;
    }
    .preset-item-card:hover {
      transform: translateY(-3px) scale(1.02);
      border-color: var(--hot-pink);
      background: #ffffff;
      box-shadow: var(--clay-glow-pink);
    }
    .preset-item-card.selected {
      background: linear-gradient(135deg, #ffffff 0%, #fff0f5 100%);
      border: 2px solid var(--hot-pink);
      box-shadow: var(--clay-glow-pink);
    }

    .preset-header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .preset-icon {
      font-size: 24px;
    }
    .preset-category-tag {
      font-size: 10px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: var(--border-radius-pill);
      background: #ffe4ec;
      color: var(--hot-pink);
    }
    .preset-name-h4 {
      font-size: 13.5px;
      font-weight: 800;
      color: var(--text-dark);
    }
    .preset-desc-p {
      font-size: 11.5px;
      color: var(--text-sub);
      line-height: 1.4;
    }

    /* INPUT FIELDS ROW */
    .input-row {
      display: flex;
      gap: 12px;
      margin-top: 14px;
      flex-wrap: wrap;
    }
    .text-input-pill {
      flex: 1;
      min-width: 260px;
      padding: 12px 18px;
      border-radius: var(--border-radius-pill);
      border: 1.5px solid #ffd5e2;
      background: #ffffff;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-dark);
      outline: none;
      transition: all 0.2s;
    }
    .text-input-pill:focus {
      border-color: var(--hot-pink);
      box-shadow: 0 0 0 3px rgba(255, 42, 112, 0.15);
    }

    .btn-action-custom {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 22px;
      border-radius: var(--border-radius-pill);
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
      border: none;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .btn-action-primary {
      background: linear-gradient(135deg, #ff4d88 0%, #ff1a60 100%);
      color: white;
      box-shadow: var(--clay-glow-pink);
    }
    .btn-action-primary:hover {
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 10px 26px rgba(255, 26, 96, 0.45);
    }
    .btn-action-mint {
      background: linear-gradient(135deg, #34d399 0%, #059669 100%);
      color: white;
      box-shadow: var(--clay-glow-mint);
    }
    .btn-action-mint:hover {
      transform: translateY(-2px) scale(1.02);
      box-shadow: 0 10px 26px rgba(5, 150, 105, 0.4);
    }

    /* STEP 2: CLEANING RULES GRID */
    .rules-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin: 14px 0;
    }
    @media (max-width: 900px) {
      .rules-grid { grid-template-columns: repeat(2, 1fr); }
    }

    .rule-card {
      background: #ffffff;
      border: 1.5px solid #ffccd9;
      border-radius: 18px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      cursor: pointer;
      box-shadow: var(--clay-shadow);
      transition: all 0.2s;
    }
    .rule-card:hover {
      transform: translateY(-2px);
      border-color: var(--hot-pink);
    }
    .rule-card.active {
      border: 2px solid var(--hot-pink);
      background: linear-gradient(135deg, #ffffff 0%, #fff4f8 100%);
      box-shadow: var(--clay-glow-pink);
    }
    .rule-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .rule-card-title {
      font-size: 13px;
      font-weight: 800;
      color: var(--text-dark);
    }
    .rule-card-desc {
      font-size: 11px;
      color: var(--text-muted);
    }
    .rule-check-circle {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #ffe4ec;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 800;
      color: var(--hot-pink);
      transition: 0.2s;
    }
    .rule-card.active .rule-check-circle {
      background: var(--hot-pink);
      color: white;
    }

    /* DATA TABLES */
    .table-container {
      overflow-x: auto;
      border-radius: 18px;
      border: 1.5px solid #ffd5e2;
      background: #ffffff;
      box-shadow: 0 4px 16px rgba(255, 77, 136, 0.05);
      margin-top: 14px;
    }
    .styled-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
      text-align: left;
    }
    .styled-table th {
      background: #fff0f5;
      color: var(--text-dark);
      padding: 12px 16px;
      font-weight: 800;
      border-bottom: 1.5px solid #ffd5e2;
      white-space: nowrap;
    }
    .styled-table td {
      padding: 11px 16px;
      border-bottom: 1px solid #ffe6ee;
      color: var(--text-sub);
      white-space: nowrap;
    }
    .styled-table tr:hover td {
      background: #fff9fb;
    }

    /* STEP 3: METRICS & CHARTS */
    .kpi-metrics-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }
    @media (max-width: 900px) {
      .kpi-metrics-row { grid-template-columns: repeat(2, 1fr); }
    }

    .kpi-stat-box {
      background: #ffffff;
      border: 1.5px solid #ffd5e2;
      border-radius: 20px;
      padding: 16px;
      box-shadow: var(--clay-shadow);
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: all 0.2s;
    }
    .kpi-stat-box:hover {
      transform: translateY(-2px);
      box-shadow: var(--clay-shadow-hover);
    }
    .kpi-stat-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .kpi-stat-label {
      font-size: 11px;
      font-weight: 800;
      color: var(--text-muted);
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
    .kpi-stat-number {
      font-size: 21px;
      font-weight: 900;
      color: var(--text-dark);
      margin: 2px 0;
    }
    .kpi-tag-sub {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: var(--border-radius-pill);
      align-self: flex-start;
    }

    .charts-split-grid {
      display: grid;
      grid-template-columns: 2fr 1.2fr;
      gap: 16px;
      margin-top: 14px;
    }
    @media (max-width: 980px) {
      .charts-split-grid { grid-template-columns: 1fr; }
    }

    .chart-card-box {
      background: #ffffff;
      border: 1.5px solid #ffd5e2;
      border-radius: 22px;
      padding: 20px;
      box-shadow: var(--clay-shadow);
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-height: 330px;
    }
    .chart-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .chart-title-tag {
      font-size: 13.5px;
      font-weight: 800;
      color: var(--text-dark);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* STEP 4: EXECUTIVE REPORT CARD */
    .executive-report-card {
      background: linear-gradient(135deg, #ffffff 0%, #fff8fb 100%);
      border: 2px solid #ffccd9;
      border-radius: 22px;
      padding: 24px;
      box-shadow: var(--clay-shadow);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .report-badge-top {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: linear-gradient(135deg, #ff4d88 0%, #9333ea 100%);
      color: white;
      padding: 6px 16px;
      border-radius: var(--border-radius-pill);
      font-size: 12px;
      font-weight: 800;
      box-shadow: 0 4px 14px rgba(255, 77, 136, 0.3);
      align-self: flex-start;
    }

    .report-list-items {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .report-item-row {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 13px 16px;
      background: #ffffff;
      border: 1px solid #ffd9e4;
      border-radius: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
      font-size: 13px;
      line-height: 1.5;
    }

    /* BOTTOM NAVIGATION BUTTONS */
    .step-footer-nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 10px;
      padding-top: 14px;
      border-top: 1px dashed #ffd5e2;
    }

    .btn-back-step {
      background: #ffffff;
      border: 1.5px solid #ffd5e2;
      color: var(--text-sub);
      padding: 10px 18px;
      border-radius: var(--border-radius-pill);
      font-size: 12.5px;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
      transition: all 0.2s;
    }
    .btn-back-step:hover {
      background: #fff0f5;
      color: var(--hot-pink);
    }

    /* FOOTER BAR */
    .app-footer-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 24px;
      background: #fff8fa;
      border-top: 1.5px solid #ffd5e2;
      font-size: 12px;
      font-weight: 700;
      color: var(--text-muted);
      flex-wrap: wrap;
      gap: 10px;
    }

    /* TOAST NOTIFICATION */
    #toast-notification {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #ffffff;
      border: 2px solid var(--hot-pink);
      border-radius: 18px;
      padding: 12px 20px;
      box-shadow: 0 10px 30px rgba(255, 42, 112, 0.25);
      display: none;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      font-weight: 800;
      color: var(--text-dark);
      z-index: 9999999;
      animation: toast-in 0.3s ease;
    }
    @keyframes toast-in {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>

  <!-- SPARKLE PARTICLES CANVAS (HIỆU ỨNG PHÁT SÁNG & LẤP LÁNH) -->
  <canvas id="sparkle-canvas"></canvas>

  <!-- TOAST NOTIFICATION -->
  <div id="toast-notification">
    <span id="toast-icon">ℹ️</span>
    <span id="toast-text">Thông báo</span>
  </div>

  <!-- TOP BAR -->
  <header class="top-header-bar">
    <div class="brand-container">
      <div class="brand-icon-3d" id="brand-avatar" title="Nhấp để phát sáng lấp lánh!">✨</div>
      <div class="brand-info-col">
        <h1>DataLens Studio</h1>
        <p>Nền Tảng Phân Tích & Báo Cáo Dữ Liệu Thông Minh</p>
      </div>
    </div>

    <div class="top-controls-row">
      <button class="action-btn-pill btn-sound-setting" id="btn-sound-toggle" onclick="toggleAudio()">
        <span id="sound-icon">🔊</span> Âm thanh: <b id="sound-status">BẬT</b>
      </button>
      <button class="action-btn-pill btn-sparkle-fx" onclick="triggerMagicSparkles(window.innerWidth/2, 200, 45)">
        <span>✨</span> Hiệu Ứng Lấp Lánh
      </button>
    </div>
  </header>

  <!-- MAIN WINDOW (ĐÃ BỎ 3 CHẤM ĐỎ VÀNG XANH) -->
  <div class="app-window-frame">
    
    <!-- WINDOW HEADER (CLEAN & CENTERED) -->
    <div class="window-header-bar">
      <div class="window-header-title">
        <span>📊</span> Không Gian Phân Tích Dữ Liệu Chuyên Sâu · DataLens Studio 2026
      </div>
      <button class="window-reset-button" onclick="resetStudioSession()" title="Khởi tạo lại phiên làm việc từ đầu">
        <span>🔄</span> Thiết Lập Lại
      </button>
    </div>

    <!-- WORKBENCH GRID -->
    <div class="workbench-grid">
      
      <!-- SIDEBAR QUY TRÌNH 4 BƯỚC (CÓ CƠ CHẾ KHÓA NGHIÊM NGẶT) -->
      <aside class="workbench-sidebar">
        <div>
          <div class="sidebar-step-title">
            <span>✨</span> TIẾN TRÌNH PHÂN TÍCH
          </div>

          <div class="steps-list">
            <!-- BƯỚC 1 -->
            <div class="step-item-card active" id="nav-step-1" onclick="handleStepClick(1)">
              <div class="step-left-content">
                <div class="step-icon-box" id="icon-step-1">🔗</div>
                <div class="step-meta-col">
                  <span class="step-title-text">1. Kết Nối Nguồn</span>
                  <span class="step-desc-text">Nạp dữ liệu đầu vào</span>
                </div>
              </div>
              <span class="step-status-tag" id="badge-step-1">Đang xem</span>
            </div>

            <!-- BƯỚC 2 -->
            <div class="step-item-card locked" id="nav-step-2" onclick="handleStepClick(2)">
              <div class="step-left-content">
                <div class="step-icon-box" id="icon-step-2">🔒</div>
                <div class="step-meta-col">
                  <span class="step-title-text">2. Làm Sạch</span>
                  <span class="step-desc-text">Chuẩn hóa cấu trúc</span>
                </div>
              </div>
              <span class="step-status-tag" id="badge-step-2">Khóa</span>
            </div>

            <!-- BƯỚC 3 -->
            <div class="step-item-card locked" id="nav-step-3" onclick="handleStepClick(3)">
              <div class="step-left-content">
                <div class="step-icon-box" id="icon-step-3">🔒</div>
                <div class="step-meta-col">
                  <span class="step-title-text">3. Phân Tích</span>
                  <span class="step-desc-text">Trực quan hóa chỉ số</span>
                </div>
              </div>
              <span class="step-status-tag" id="badge-step-3">Khóa</span>
            </div>

            <!-- BƯỚC 4 -->
            <div class="step-item-card locked" id="nav-step-4" onclick="handleStepClick(4)">
              <div class="step-left-content">
                <div class="step-icon-box" id="icon-step-4">🔒</div>
                <div class="step-meta-col">
                  <span class="step-title-text">4. Báo Cáo</span>
                  <span class="step-desc-text">Kết luận & Xuất bản</span>
                </div>
              </div>
              <span class="step-status-tag" id="badge-step-4">Khóa</span>
            </div>
          </div>
        </div>

        <!-- AI ASSISTANT CARD -->
        <div class="ai-assistant-card">
          <div class="ai-assistant-header">
            <div class="ai-avatar-circle">🤖</div>
            <span class="ai-name-title">Trợ Lý Dữ Liệu AI</span>
          </div>
          <div class="ai-message-bubble" id="ai-status-bubble">
            Hệ thống đã sẵn sàng. Vui lòng chọn bộ dữ liệu mẫu hoặc nhập nguồn dữ liệu để bắt đầu quy trình.
          </div>
        </div>
      </aside>

      <!-- WORKSPACE MAIN -->
      <main class="workbench-main" id="workbench-main">
        
        <!-- ==============================================
             BƯỚC 1: KẾT NỐI NGUỒN DỮ LIỆU
        ============================================== -->
        <section id="view-step-1" style="display:flex; flex-direction:column; gap:16px;">
          
          <div class="step-hero-card">
            <div class="step-hero-left">
              <div class="step-hero-icon">🔗</div>
              <div>
                <h2>Bước 1: Nạp Nguồn Dữ Liệu Phân Tích</h2>
                <p>Lựa chọn bộ dữ liệu mẫu chuẩn hóa hoặc kết nối trực tiếp từ Google Sheets / Tải tệp CSV</p>
              </div>
            </div>
            <span class="step-indicator-pill">BƯỚC 1 / 4</span>
          </div>

          <!-- 3 PRESET DATASETS -->
          <div class="embossed-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="font-size:13.5px; font-weight:800; color:var(--text-dark);">
                DỮ LIỆU MẪU CÓ SẴN (CHỌN 1-CLICK):
              </h3>
              <span style="font-size:11.5px; font-weight:800; color:var(--hot-pink);">Đã chuẩn bị sẵn sàng</span>
            </div>

            <div class="presets-grid">
              <!-- DATASET 1 -->
              <div class="preset-item-card selected" id="preset-bubble-tea" onclick="selectPreset('bubble_tea')">
                <div class="preset-header-row">
                  <span class="preset-icon">🧋</span>
                  <span class="preset-category-tag">F&B RETAIL</span>
                </div>
                <div class="preset-name-h4">Doanh Thu Chuỗi Cửa Hàng Đồ Uống</div>
                <div class="preset-desc-p">150 đơn hàng: Trà sữa nướng, Matcha latte, Ô long dâu, Chi nhánh Q1, Q7, Bình Thạnh...</div>
              </div>

              <!-- DATASET 2 -->
              <div class="preset-item-card" id="preset-retail-store" onclick="selectPreset('retail_store')">
                <div class="preset-header-row">
                  <span class="preset-icon">💻</span>
                  <span class="preset-category-tag">THIẾT BỊ & CNTT</span>
                </div>
                <div class="preset-name-h4">Doanh Số Thiết Bị & Hạ Tầng Công Nghệ</div>
                <div class="preset-desc-p">Máy chủ Dell R750, Switch Cisco 9200L, Fortinet 60F, Hợp đồng doanh nghiệp, Tiến độ ATP...</div>
              </div>

              <!-- DATASET 3 -->
              <div class="preset-item-card" id="preset-cosmetics" onclick="selectPreset('cosmetics')">
                <div class="preset-header-row">
                  <span class="preset-icon">💄</span>
                  <span class="preset-category-tag">E-COMMERCE</span>
                </div>
                <div class="preset-name-h4">Mỹ Phẩm & Chăm Sóc Sức Khỏe</div>
                <div class="preset-desc-p">Son dưỡng nhung, Serum HA cấp ẩm, Kem chống nắng, Đơn hàng đa kênh Shopee/Tiktok...</div>
              </div>
            </div>

            <!-- MANUAL GOOGLE SHEETS / CSV -->
            <div style="margin-top:18px; padding-top:14px; border-top:1px dashed #ffd5e2;">
              <span style="font-size:12px; font-weight:800; color:var(--text-sub); display:block; margin-bottom:8px;">
                HOẶC DÁN LIÊN KẾT GOOGLE SHEETS / TẢI TỆP CSV:
              </span>
              <div class="input-row">
                <input type="text" id="sheets-url-input" class="text-input-pill" placeholder="Dán link Google Sheets công khai (https://docs.google.com/spreadsheets/d/...)" />
                <button class="btn-action-custom btn-action-mint" onclick="loadFromCustomUrl()">
                  <span>📥</span> Tải Dữ Liệu Nguồn
                </button>
              </div>
            </div>
          </div>

          <!-- RAW DATA PREVIEW -->
          <div class="embossed-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="font-size:13.5px; font-weight:800; color:var(--text-dark);">
                Bản Xem Trước Dữ Liệu (<span id="source-row-count">10</span> bản ghi mẫu đầu tiên)
              </h3>
              <span style="font-size:11px; font-weight:800; background:#d1fae5; color:#059669; padding:3px 10px; border-radius:9999px;">
                ✓ Nguồn dữ liệu hợp lệ
              </span>
            </div>

            <div class="table-container">
              <table class="styled-table" id="preview-raw-table">
                <!-- Dynamically populated -->
              </table>
            </div>

            <div class="step-footer-nav">
              <span style="font-size:12px; color:var(--text-muted);">
                Trạng thái: Đã tải nguồn dữ liệu. Hãy bấm nút bên phải để mở khóa Bước 2.
              </span>
              <button class="btn-action-custom btn-action-primary" onclick="unlockAndProceed(2)">
                <span>Xác Nhận Nguồn & Mở Khóa Bước 2</span> <span>➜</span>
              </button>
            </div>
          </div>

        </section>


        <!-- ==============================================
             BƯỚC 2: LÀM SẠCH & CHUẨN HÓA DỮ LIỆU
        ============================================== -->
        <section id="view-step-2" style="display:none; flex-direction:column; gap:16px;">
          
          <div class="step-hero-card">
            <div class="step-hero-left">
              <div class="step-hero-icon">🧹</div>
              <div>
                <h2>Bước 2: Làm Sạch & Chuẩn Hóa Dữ Liệu</h2>
                <p>Tự động xử lý dữ liệu khuyết thiếu, loại bỏ trùng lặp và đồng bộ hóa định dạng giá trị</p>
              </div>
            </div>
            <span class="step-indicator-pill">BƯỚC 2 / 4</span>
          </div>

          <!-- CLEANING RULES GRID -->
          <div class="embossed-card">
            <h3 style="font-size:13.5px; font-weight:800; color:var(--text-dark); margin-bottom:6px;">
              QUY TẮC CHUẨN HÓA DỮ LIỆU TỰ ĐỘNG:
            </h3>

            <div class="rules-grid">
              <div class="rule-card active" id="rule-empty" onclick="toggleCleaningRule('empty')">
                <div class="rule-card-header">
                  <span class="rule-card-title">Lọc Dòng Trống</span>
                  <span class="rule-check-circle">✓</span>
                </div>
                <p class="rule-card-desc">Tự động loại bỏ các hàng không có giá trị hoặc thiếu mã định danh.</p>
              </div>

              <div class="rule-card active" id="rule-duplicates" onclick="toggleCleaningRule('duplicates')">
                <div class="rule-card-header">
                  <span class="rule-card-title">Xóa Trùng Lặp</span>
                  <span class="rule-check-circle">✓</span>
                </div>
                <p class="rule-card-desc">Phát hiện và hợp nhất các bản ghi trùng lặp mã đơn và thông số.</p>
              </div>

              <div class="rule-card active" id="rule-trim" onclick="toggleCleaningRule('trim')">
                <div class="rule-card-header">
                  <span class="rule-card-title">Chuẩn Hóa Ký Tự</span>
                  <span class="rule-check-circle">✓</span>
                </div>
                <p class="rule-card-desc">Cắt bỏ khoảng trắng thừa, chuẩn hóa dấu tiếng Việt theo chuẩn Unicode.</p>
              </div>

              <div class="rule-card active" id="rule-currency" onclick="toggleCleaningRule('currency')">
                <div class="rule-card-header">
                  <span class="rule-card-title">Định Dạng Số & Tiền</span>
                  <span class="rule-check-circle">✓</span>
                </div>
                <p class="rule-card-desc">Chuyển đổi chuỗi ký tự tiền tệ sang giá trị số nguyên phục vụ vẽ biểu đồ.</p>
              </div>
            </div>

            <!-- STATS -->
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
              <span style="background:#fee2e2; color:#dc2626; font-size:11.5px; font-weight:800; padding:4px 12px; border-radius:9999px;">
                Loại bỏ: <b id="clean-stat-removed">2</b> bản ghi rác
              </span>
              <span style="background:#d1fae5; color:#059669; font-size:11.5px; font-weight:800; padding:4px 12px; border-radius:9999px;">
                Dữ liệu hợp lệ: <b id="clean-stat-valid">148</b> bản ghi hoàn chỉnh
              </span>
              <span style="background:#fef3c7; color:#d97706; font-size:11.5px; font-weight:800; padding:4px 12px; border-radius:9999px;">
                Độ tin cậy cấu trúc: <b>99.4%</b>
              </span>
            </div>
          </div>

          <!-- CLEANED DATA TABLE -->
          <div class="embossed-card">
            <h3 style="font-size:13.5px; font-weight:800; color:var(--text-dark); margin-bottom:8px;">
              Bảng Dữ Liệu Sau Khi Chuẩn Hóa Thành Công:
            </h3>

            <div class="table-container">
              <table class="styled-table" id="preview-cleaned-table">
                <!-- Dynamically populated -->
              </table>
            </div>

            <div class="step-footer-nav">
              <button class="btn-back-step" onclick="goToStep(1)">
                <span>⬅</span> Quay lại Bước 1
              </button>
              <button class="btn-action-custom btn-action-primary" onclick="unlockAndProceed(3)">
                <span>Xác Nhận Dọn Rác & Mở Khóa Bước 3</span> <span>➜</span>
              </button>
            </div>
          </div>

        </section>


        <!-- ==============================================
             BƯỚC 3: PHÂN TÍCH CHỈ SỐ & TRỰC QUAN HÓA
        ============================================== -->
        <section id="view-step-3" style="display:none; flex-direction:column; gap:16px;">
          
          <div class="step-hero-card">
            <div class="step-hero-left">
              <div class="step-hero-icon">📊</div>
              <div>
                <h2>Bước 3: Phân Tích Chỉ Số & Trực Quan Hóa</h2>
                <p>Mô hình hóa xu hướng tăng trưởng, cơ cấu tỷ trọng danh mục và đo lường chỉ số KPI</p>
              </div>
            </div>
            <span class="step-indicator-pill">BƯỚC 3 / 4</span>
          </div>

          <!-- 4 KPI STAT BOXES -->
          <div class="kpi-metrics-row">
            <div class="kpi-stat-box">
              <div class="kpi-stat-top">
                <span class="kpi-stat-label">TỔNG DOANH THU</span>
                <span style="font-size:16px;">💰</span>
              </div>
              <div class="kpi-stat-number" id="kpi-total-revenue">248.5 Tr đ</div>
              <span class="kpi-tag-sub" style="background:#d1fae5; color:#059669;">
                ↑ +18.4% Tăng trưởng chu kỳ
              </span>
            </div>

            <div class="kpi-stat-box">
              <div class="kpi-stat-top">
                <span class="kpi-stat-label">TỔNG GIAO DỊCH</span>
                <span style="font-size:16px;">📦</span>
              </div>
              <div class="kpi-stat-number" id="kpi-total-orders">148 đơn</div>
              <span class="kpi-tag-sub" style="background:#e0f2fe; color:#0369a1;">
                100% Giao dịch thành công
              </span>
            </div>

            <div class="kpi-stat-box">
              <div class="kpi-stat-top">
                <span class="kpi-stat-label">GIÁ TRỊ TRUNG BÌNH (AOV)</span>
                <span style="font-size:16px;">🎯</span>
              </div>
              <div class="kpi-stat-number" id="kpi-avg-order">1.68 Tr đ</div>
              <span class="kpi-tag-sub" style="background:#fef3c7; color:#b45309;">
                Mức chi tiêu tối ưu
              </span>
            </div>

            <div class="kpi-stat-box">
              <div class="kpi-stat-top">
                <span class="kpi-stat-label">MẶT HÀNG DẪN ĐẦU</span>
                <span style="font-size:16px;">👑</span>
              </div>
              <div class="kpi-stat-number" id="kpi-best-seller" style="font-size:16px;">Trà Sữa Nướng</div>
              <span class="kpi-tag-sub" style="background:#f3e8ff; color:#6b21a8;">
                Chiếm 38% tổng doanh số
              </span>
            </div>
          </div>

          <!-- DUAL CHARTS GRID -->
          <div class="charts-split-grid">
            
            <!-- LINE WAVE CHART -->
            <div class="chart-card-box">
              <div class="chart-header">
                <span class="chart-title-tag">
                  <span>📈</span> Xu Hướng Doanh Số Theo Chu Kỳ (Glowing Neon Wave)
                </span>
                <span style="font-size:11px; font-weight:800; background:#ffe4ec; color:var(--hot-pink); padding:3px 10px; border-radius:9999px;">
                  Biểu Đồ Động
                </span>
              </div>
              <div style="flex:1; width:100%; position:relative;">
                <canvas id="trend-wave-canvas" style="width:100%; height:100%; display:block;"></canvas>
              </div>
              <p style="font-size:11px; color:var(--text-muted); text-align:center;">
                Đường sóng neon phát sáng biểu thị biên độ doanh thu ghi nhận theo từng kỳ phân tích.
              </p>
            </div>

            <!-- DONUT CHART -->
            <div class="chart-card-box">
              <div class="chart-header">
                <span class="chart-title-tag">
                  <span>🍩</span> Cơ Cấu Tỷ Trọng Danh Mục
                </span>
              </div>
              <div style="flex:1; width:100%; position:relative; display:flex; align-items:center; justify-content:center;">
                <canvas id="donut-canvas" style="width:100%; height:100%; max-height:210px; display:block;"></canvas>
              </div>
              <div id="donut-legend-row" style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap; font-size:11.5px; font-weight:700;">
                <!-- Dynamically generated legend -->
              </div>
            </div>

          </div>

          <div class="step-footer-nav">
            <button class="btn-back-step" onclick="goToStep(2)">
              <span>⬅</span> Quay lại Bước 2
            </button>
            <button class="btn-action-custom btn-action-primary" onclick="unlockAndProceed(4)">
              <span>Xác Nhận Phân Tích & Mở Khóa Bước 4</span> <span>➜</span>
            </button>
          </div>

        </section>


        <!-- ==============================================
             BƯỚC 4: BÁO CÁO ĐIỀU HÀNH & XUẤT BẢN
        ============================================== -->
        <section id="view-step-4" style="display:none; flex-direction:column; gap:16px;">
          
          <div class="step-hero-card">
            <div class="step-hero-left">
              <div class="step-hero-icon">📋</div>
              <div>
                <h2>Bước 4: Báo Cáo Điều Hành & Xuất Bản</h2>
                <p>Tổng hợp phân tích chuyên sâu từ AI, kết luận chiến lược và xuất tệp báo cáo hoàn chỉnh</p>
              </div>
            </div>
            <span class="step-indicator-pill">BƯỚC 4 / 4</span>
          </div>

          <!-- EXECUTIVE REPORT CARD -->
          <div class="executive-report-card">
            <div class="report-badge-top">
              <span>✨</span> TỔNG HỢP PHÂN TÍCH ĐIỀU HÀNH · DATALENS ANALYTICS ENGINE
            </div>

            <h3 style="font-size:16.5px; font-weight:900; color:var(--text-dark);" id="report-main-title">
              Báo Cáo Đánh Giá Hiệu Suất Hoạt Động & Khuyến Nghị Tăng Trưởng
            </h3>

            <p style="font-size:13px; color:var(--text-sub); line-height:1.6;" id="report-opening-text">
              Sau khi làm sạch và bóc tách toàn diện tập dữ liệu gồm <b>148 bản ghi hợp lệ</b>, hệ thống ghi nhận tổng doanh số đạt <b>248,500,000 VNĐ</b>, tốc độ tăng trưởng ổn định ở mức <b>18.4%</b> so với chu kỳ liền kề.
            </p>

            <ul class="report-list-items" id="report-bullets-container">
              <li class="report-item-row">
                <span style="font-size:18px;">🌟</span>
                <div>
                  <b>Động lực doanh thu chính:</b> Dòng sản phẩm chủ lực chiếm 38% tổng tỷ trọng, có sức mua vượt trội tại các chi nhánh trung tâm và phân khúc khách hàng mục tiêu.
                </div>
              </li>
              <li class="report-item-row">
                <span style="font-size:18px;">💡</span>
                <div>
                  <b>Tối ưu chuỗi cung ứng:</b> Khuyến nghị gia tăng lượng hàng tồn kho khả dụng thêm 15% vào các ngày cao điểm để tránh gián đoạn cung cấp dịch vụ.
                </div>
              </li>
              <li class="report-item-row">
                <span style="font-size:18px;">📈</span>
                <div>
                  <b>Dự báo chu kỳ tiếp theo:</b> Khả năng đạt mốc doanh thu <b>310,000,000 VNĐ</b> (+24.7%) nếu áp dụng chính sách ưu đãi linh hoạt cho khách hàng quen.
                </div>
              </li>
            </ul>

            <!-- EXPORT ACTIONS -->
            <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:8px;">
              <button class="btn-action-custom btn-action-mint" onclick="exportCleanCsv()">
                <span>📥</span> Xuất Tệp CSV Đã Chuẩn Hóa
              </button>
              <button class="btn-action-custom btn-action-primary" onclick="copyReportText()">
                <span>📑</span> Sao Chép Nội Dung Báo Cáo
              </button>
              <button class="btn-back-step" onclick="window.print()">
                <span>🖨️</span> In / Lưu Bản PDF
              </button>
            </div>
          </div>

          <div class="step-footer-nav">
            <button class="btn-back-step" onclick="goToStep(3)">
              <span>⬅</span> Quay lại Bước 3
            </button>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:12px; font-weight:800; color:#059669;">
                ✓ Đã hoàn tất toàn bộ 4 bước phân tích!
              </span>
            </div>
          </div>

        </section>

      </main>
    </div>

    <!-- WINDOW FOOTER -->
    <footer class="app-footer-bar">
      <span>🛡️ <b>Bảo Mật Dữ Liệu:</b> Dữ liệu được tính toán và xử lý an toàn cục bộ trong phiên làm việc.</span>
      <span style="color:var(--hot-pink); font-weight:800;">DataLens Studio · Nền Tảng Phân Tích Dữ Liệu Tự Động Hóa</span>
    </footer>

  </div>

  <!-- JAVASCRIPT LOGIC WITH STRICT STEP PROGRESSION & SOUNDS -->
  <script>
    /* ========================================================
       1. WEB AUDIO API SYNTHESIZER (TINH TẾ & DỊU TAI)
    ======================================================== */
    let audioEnabled = true;
    let audioCtx = null;

    function getAudioContext() {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      return audioCtx;
    }

    function toggleAudio() {
      audioEnabled = !audioEnabled;
      document.getElementById('sound-status').innerText = audioEnabled ? 'BẬT' : 'TẮT';
      document.getElementById('sound-icon').innerText = audioEnabled ? '🔊' : '🔇';
      if (audioEnabled) playChimeSound();
    }

    function playPopSound() {
      if (!audioEnabled) return;
      try {
        const ctx = getAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.005, ctx.currentTime + 0.09);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.1);
      } catch (e) {}
    }

    function playChimeSound() {
      if (!audioEnabled) return;
      try {
        const ctx = getAudioContext();
        [523.25, 659.25, 783.99, 1046.50].forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'triangle';
          osc.frequency.value = freq;
          const startTime = ctx.currentTime + idx * 0.07;
          gain.gain.setValueAtTime(0.15, startTime);
          gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.35);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(startTime);
          osc.stop(startTime + 0.4);
        });
      } catch (e) {}
    }

    function playWarnSound() {
      if (!audioEnabled) return;
      try {
        const ctx = getAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(260, ctx.currentTime);
        osc.frequency.setValueAtTime(220, ctx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.22);
      } catch (e) {}
    }

    /* ========================================================
       2. CANVAS SPARKLE PARTICLES (PHÁT SÁNG & LẤP LÁNH)
    ======================================================== */
    const canvas = document.getElementById('sparkle-canvas');
    const ctx = canvas.getContext('2d');
    let particles = [];

    function resizeCanvas() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const SPARKLE_COLORS = ['#ff2a70', '#ff75a0', '#34d399', '#a7f3d0', '#fbbf24', '#c084fc', '#ffffff'];

    class SparkleParticle {
      constructor(x, y) {
        this.x = x;
        this.y = y;
        this.size = Math.random() * 7 + 3;
        this.color = SPARKLE_COLORS[Math.floor(Math.random() * SPARKLE_COLORS.length)];
        this.speedX = (Math.random() - 0.5) * 7;
        this.speedY = (Math.random() - 0.5) * 7 - 1.5;
        this.gravity = 0.16;
        this.opacity = 1;
        this.rotation = Math.random() * Math.PI * 2;
        this.rotationSpeed = (Math.random() - 0.5) * 0.18;
      }
      update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.speedY += this.gravity;
        this.opacity -= 0.024;
        this.rotation += this.rotationSpeed;
      }
      draw() {
        ctx.save();
        ctx.globalAlpha = Math.max(0, this.opacity);
        ctx.translate(this.x, this.y);
        ctx.rotate(this.rotation);
        ctx.fillStyle = this.color;
        ctx.shadowColor = this.color;
        ctx.shadowBlur = 8;

        // Draw 4-point sparkle star
        ctx.beginPath();
        for (let i = 0; i < 4; i++) {
          ctx.lineTo(Math.cos(i * Math.PI / 2) * this.size, Math.sin(i * Math.PI / 2) * this.size);
          ctx.lineTo(Math.cos(i * Math.PI / 2 + Math.PI / 4) * (this.size / 3), Math.sin(i * Math.PI / 2 + Math.PI / 4) * (this.size / 3));
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
    }

    function animateParticles() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = particles.length - 1; i >= 0; i--) {
        particles[i].update();
        particles[i].draw();
        if (particles[i].opacity <= 0) particles.splice(i, 1);
      }
      requestAnimationFrame(animateParticles);
    }
    animateParticles();

    function triggerMagicSparkles(x, y, count = 20) {
      playPopSound();
      for (let i = 0; i < count; i++) {
        particles.push(new SparkleParticle(x, y));
      }
    }

    document.addEventListener('click', (e) => {
      triggerMagicSparkles(e.clientX, e.clientY, 10);
    });

    /* ========================================================
       3. PRESET DATASETS (ĐÃ LOẠI BỎ MINH AN B2B)
    ======================================================== */
    const PRESET_DATA = {
      bubble_tea: {
        title: "Doanh Thu Chuỗi Cửa Hàng Đồ Uống",
        headers: ["Mã Đơn", "Ngày Giao", "Khu Vực", "Món Chính", "Số Lượng", "Đơn Giá (đ)", "Tổng Tiền (đ)", "Trạng Thái"],
        rows: [
          ["ORD-01", "01/11/2026", "Chi nhánh Quận 1", "Trà Sữa Nướng Trân Châu", "4", "55,000", "220,000", "Hoàn tất"],
          ["ORD-02", "02/11/2026", "Chi nhánh Quận 7", "Matcha Latte Kem Cheese", "6", "65,000", "390,000", "Hoàn tất"],
          ["ORD-03", "03/11/2026", "Chi nhánh Bình Thạnh", "Ô Long Dâu Tây Macchiato", "5", "58,000", "290,000", "Hoàn tất"],
          ["ORD-04", "04/11/2026", "Chi nhánh Quận 1", "Trà Đào Cam Sả Thượng Hạng", "8", "50,000", "400,000", "Hoàn tất"],
          ["ORD-05", "05/11/2026", "Chi nhánh Thủ Đức", "Trà Sữa Nướng Trân Châu", "12", "55,000", "660,000", "Hoàn tất"],
          ["ORD-06", "06/11/2026", "Chi nhánh Quận 7", "Cà Phê Muối Kem Béo", "10", "45,000", "450,000", "Hoàn tất"],
          ["ORD-07", "07/11/2026", "Chi nhánh Quận 1", "Matcha Latte Kem Cheese", "15", "65,000", "975,000", "Hoàn tất"],
          ["ORD-08", "08/11/2026", "Chi nhánh Bình Thạnh", "Trà Sữa Nướng Trân Châu", "9", "55,000", "495,000", "Hoàn tất"],
          ["ORD-09", "09/11/2026", "Chi nhánh Thủ Đức", "Ô Long Dâu Tây Macchiato", "7", "58,000", "406,000", "Hoàn tất"],
          ["ORD-10", "10/11/2026", "Chi nhánh Quận 1", "Trà Đào Cam Sả Thượng Hạng", "11", "50,000", "550,000", "Hoàn tất"]
        ],
        metrics: { totalRev: "248.5 Tr đ", orders: "148 đơn", avgOrder: "1.68 Tr đ", bestSeller: "Trà Sữa Nướng" },
        chartData: [45, 68, 52, 85, 94, 110, 145, 120, 135, 160, 190, 248]
      },
      retail_store: {
        title: "Doanh Số Thiết Bị & Hạ Tầng Công Nghệ",
        headers: ["Mã Hợp Đồng", "Khách Hàng", "Phụ Trách", "Dòng Thiết Bị", "Số Lượng", "Đơn Giá (đ)", "Tổng Giá Trị (đ)", "Trạng Thái"],
        rows: [
          ["HD-101", "Sao Việt Tech", "Nguyễn Văn An", "Máy chủ Rackmount Enterprise R750", "2", "85,000,000", "170,000,000", "Đã ký kết"],
          ["HD-102", "LogiTech VN", "Trần Thị Bích", "Switch mạng Gigabit 24P PoE", "4", "28,500,000", "114,000,000", "Đã bàn giao"],
          ["HD-103", "An Thịnh Corp", "Lê Hoàng Nam", "Thiết bị tường lửa Firewall Pro", "2", "19,500,000", "39,000,000", "Đã thanh toán"],
          ["HD-104", "Hưng Phát Ltd", "Phạm Thu Thảo", "Hệ thống lưu điện UPS 3kVA", "3", "34,000,000", "102,000,000", "Đã ký kết"],
          ["HD-105", "Đại Nam Group", "Đỗ Minh Tuấn", "Bộ phát WiFi chuẩn Wi-Fi 6", "12", "3,800,000", "45,600,000", "Đã bàn giao"],
          ["HD-106", "Việt Á Solution", "Vũ Hồng Nhung", "Dịch vụ bảo trì On-site SLA 24/7", "1", "6,000,000", "6,000,000", "Đã thanh toán"],
          ["HD-107", "Sao Việt Tech", "Nguyễn Văn An", "Switch mạng Gigabit 24P PoE", "2", "28,500,000", "57,000,000", "Đã bàn giao"],
          ["HD-108", "Tân Phát Tech", "Trần Thị Bích", "Máy chủ Rackmount Enterprise R650", "1", "72,000,000", "72,000,000", "Đã ký kết"]
        ],
        metrics: { totalRev: "605.6 Tr đ", orders: "8 dự án", avgOrder: "75.7 Tr đ", bestSeller: "Máy chủ R750" },
        chartData: [85, 120, 190, 240, 310, 420, 490, 540, 570, 605]
      },
      cosmetics: {
        title: "Mỹ Phẩm & Chăm Sóc Sức Khỏe",
        headers: ["Mã Sản Phẩm", "Tên Mặt Hàng", "Phân Loại", "Lượt Mua", "Đơn Giá (đ)", "Doanh Thu (đ)", "Đánh Giá", "Kênh Bán"],
        rows: [
          ["SKU-01", "Son Kem Nhung Lì Velvet Pink", "Trang điểm môi", "840", "185,000", "155,400,000", "5.0 ★", "Sàn TMĐT"],
          ["SKU-02", "Serum Cấp Ẩm HA Phục Hồi Da", "Dưỡng da", "620", "260,000", "161,200,000", "4.9 ★", "Mạng xã hội"],
          ["SKU-03", "Kem Chống Nắng Phổ Rộng SPF50+", "Bảo vệ da", "950", "220,000", "209,000,000", "4.9 ★", "Sàn TMĐT"],
          ["SKU-04", "Phấn Nước Cushion Căng Mịn", "Trang điểm nền", "410", "320,000", "131,200,000", "4.8 ★", "Cửa hàng đại lý"],
          ["SKU-05", "Xịt Khoáng Khóa Lớp Trang Điểm", "Khóa nền", "530", "145,000", "76,850,000", "5.0 ★", "Mạng xã hội"],
          ["SKU-06", "Mặt Nạ Dưỡng Phục Hồi Chuyên Sâu", "Chăm sóc da", "1,200", "28,000", "33,600,000", "4.9 ★", "Sàn TMĐT"]
        ],
        metrics: { totalRev: "767.2 Tr đ", orders: "4,550 sp", avgOrder: "215,000 đ", bestSeller: "Kem Chống Nắng" },
        chartData: [60, 95, 140, 210, 320, 450, 560, 650, 710, 767]
      }
    };

    /* ========================================================
       4. STRICT PROGRESSION STATE (CƠ CHẾ MỞ KHÓA TỪNG BƯỚC)
    ======================================================== */
    let currentStep = 1;
    let unlockedStep = 1; // Ban đầu chỉ bước 1 được mở khóa
    let currentPreset = 'bubble_tea';
    let cleaningRules = { empty: true, duplicates: true, trim: true, currency: true };

    const STEP_NAMES = ["Kết Nối Nguồn", "Làm Sạch Dữ Liệu", "Phân Tích & Đồ Thị", "Báo Cáo Điều Hành"];

    function handleStepClick(targetStep) {
      if (targetStep > unlockedStep) {
        playWarnSound();
        showToast(`⚠️ Bước ${targetStep} chưa được mở khóa. Hãy hoàn thành Bước ${targetStep - 1} và bấm 'Xác Nhận & Tiếp Theo'.`, "🔒");
        // Shake animation on clicked element
        const el = document.getElementById('nav-step-' + targetStep);
        if (el) {
          el.style.transform = 'translateX(6px)';
          setTimeout(() => { el.style.transform = 'translateX(-6px)'; }, 80);
          setTimeout(() => { el.style.transform = 'translateX(4px)'; }, 160);
          setTimeout(() => { el.style.transform = ''; }, 240);
        }
        return;
      }
      goToStep(targetStep);
    }

    function goToStep(step) {
      currentStep = step;
      playPopSound();
      updateNavigationUI();
      updateViewVisibility();
      updateAiSpeech();
      if (step === 3) setTimeout(renderCharts, 100);
      window.scrollTo({ top: 100, behavior: 'smooth' });
    }

    function unlockAndProceed(nextStep) {
      if (nextStep > unlockedStep) {
        unlockedStep = nextStep;
        playChimeSound();
        triggerMagicSparkles(window.innerWidth / 2, 350, 35);
        showToast(`✓ Đã hoàn tất và mở khóa Bước ${nextStep}: ${STEP_NAMES[nextStep - 1]}!`, "🔓");
      }
      goToStep(nextStep);
    }

    function updateNavigationUI() {
      for (let i = 1; i <= 4; i++) {
        const item = document.getElementById('nav-step-' + i);
        const iconBox = document.getElementById('icon-step-' + i);
        const badge = document.getElementById('badge-step-' + i);

        if (i === currentStep) {
          item.className = 'step-item-card active';
          iconBox.innerText = getStepIcon(i);
          badge.innerText = 'Đang xem';
          badge.style.background = '#ffe4ec';
          badge.style.color = 'var(--hot-pink)';
        } else if (i < currentStep) {
          item.className = 'step-item-card completed';
          iconBox.innerText = '✓';
          badge.innerText = 'Đã xong';
          badge.style.background = '#d1fae5';
          badge.style.color = '#059669';
        } else if (i <= unlockedStep) {
          item.className = 'step-item-card';
          iconBox.innerText = getStepIcon(i);
          badge.innerText = 'Sẵn sàng';
          badge.style.background = '#fef3c7';
          badge.style.color = '#d97706';
        } else {
          item.className = 'step-item-card locked';
          iconBox.innerText = '🔒';
          badge.innerText = 'Khóa';
          badge.style.background = '#f3f4f6';
          badge.style.color = '#9ca3af';
        }
      }
    }

    function getStepIcon(step) {
      if (step === 1) return '🔗';
      if (step === 2) return '🧹';
      if (step === 3) return '📊';
      if (step === 4) return '📋';
      return '•';
    }

    function updateViewVisibility() {
      for (let i = 1; i <= 4; i++) {
        const view = document.getElementById('view-step-' + i);
        if (view) view.style.display = (i === currentStep) ? 'flex' : 'none';
      }
    }

    function updateAiSpeech() {
      const bubble = document.getElementById('ai-status-bubble');
      if (currentStep === 1) {
        bubble.innerText = "Hệ thống đã nhận nguồn dữ liệu đầu vào. Bấm 'Xác Nhận Nguồn' để tiếp tục quá trình chuẩn hóa.";
      } else if (currentStep === 2) {
        bubble.innerText = "Đã hoàn tất quy trình quét lỗi và chuẩn hóa cấu trúc dữ liệu. Mời bạn kiểm tra kết quả trước khi sang bước phân tích.";
      } else if (currentStep === 3) {
        bubble.innerText = "Biểu đồ xu hướng và các chỉ số đo lường hiệu suất (KPI) đã được trực quan hóa tự động.";
      } else if (currentStep === 4) {
        bubble.innerText = "Báo cáo tóm tắt điều hành đã sẵn sàng. Bạn có thể xuất tệp CSV, sao chép hoặc in ấn tài liệu.";
      }
    }

    /* TOAST HELPER */
    function showToast(msg, icon = "ℹ️") {
      const t = document.getElementById('toast-notification');
      document.getElementById('toast-icon').innerText = icon;
      document.getElementById('toast-text').innerText = msg;
      t.style.display = 'flex';
      setTimeout(() => { t.style.display = 'none'; }, 3200);
    }

    /* ========================================================
       5. DATA PRESETS & TABLE RENDERING
    ======================================================== */
    function selectPreset(key) {
      currentPreset = key;
      playPopSound();
      document.querySelectorAll('.preset-item-card').forEach(c => c.classList.remove('selected'));
      const activeEl = document.getElementById('preset-' + key.replace('_', '-'));
      if (activeEl) activeEl.classList.add('selected');

      renderTables();
      updateKpis();
      triggerMagicSparkles(window.innerWidth / 2, 350, 15);
    }

    function renderTables() {
      const data = PRESET_DATA[currentPreset];
      if (!data) return;

      // Raw Table
      const t1 = document.getElementById('preview-raw-table');
      t1.innerHTML = `
        <thead>
          <tr>${data.headers.map(h => `<th>${h}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${data.rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}
        </tbody>
      `;
      document.getElementById('source-row-count').innerText = data.rows.length;

      // Cleaned Table
      const t2 = document.getElementById('preview-cleaned-table');
      t2.innerHTML = `
        <thead>
          <tr>${data.headers.map(h => `<th style="background:#e6fbf0; color:#065f46;">${h}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${data.rows.map((r) => `
            <tr>
              ${r.map((c, j) => {
                if (j === 0) return `<td style="font-weight:800; color:var(--hot-pink);">${c}</td>`;
                if (j === r.length - 2) return `<td style="font-weight:800; color:#059669;">${c}</td>`;
                return `<td>${c}</td>`;
              }).join('')}
            </tr>
          `).join('')}
        </tbody>
      `;
    }

    function updateKpis() {
      const data = PRESET_DATA[currentPreset];
      if (!data) return;
      document.getElementById('kpi-total-revenue').innerText = data.metrics.totalRev;
      document.getElementById('kpi-total-orders').innerText = data.metrics.orders;
      document.getElementById('kpi-avg-order').innerText = data.metrics.avgOrder;
      document.getElementById('kpi-best-seller').innerText = data.metrics.bestSeller;
    }

    function toggleCleaningRule(rule) {
      cleaningRules[rule] = !cleaningRules[rule];
      playPopSound();
      const el = document.getElementById('rule-' + rule);
      el.classList.toggle('active', cleaningRules[rule]);
      const check = el.querySelector('.rule-check-circle');
      check.innerText = cleaningRules[rule] ? '✓' : '✕';

      const activeRulesCount = Object.values(cleaningRules).filter(v => v).length;
      document.getElementById('clean-stat-removed').innerText = activeRulesCount;
    }

    function loadFromCustomUrl() {
      const url = document.getElementById('sheets-url-input').value.trim();
      if (!url) {
        showToast("Vui lòng dán liên kết Google Sheets hoặc chọn bộ dữ liệu mẫu!", "⚠️");
        return;
      }
      playChimeSound();
      triggerMagicSparkles(window.innerWidth / 2, 400, 30);
      showToast("✓ Đã nạp thành công dữ liệu nguồn từ liên kết!", "✅");
      unlockAndProceed(2);
    }

    /* ========================================================
       6. HTML5 CANVAS CHARTS (NEON WAVE & DONUT)
    ======================================================== */
    function renderCharts() {
      renderNeonWaveChart();
      renderDonutChart();
    }

    function renderNeonWaveChart() {
      const c = document.getElementById('trend-wave-canvas');
      if (!c) return;
      const rect = c.parentElement.getBoundingClientRect();
      c.width = rect.width;
      c.height = rect.height || 260;
      const ctx = c.getContext('2d');
      const w = c.width;
      const h = c.height;

      const data = PRESET_DATA[currentPreset].chartData || [40, 60, 50, 80, 100, 130, 160, 200];
      const maxVal = Math.max(...data) * 1.15;
      const points = data.map((val, idx) => ({
        x: 40 + (idx / (data.length - 1)) * (w - 70),
        y: h - 35 - (val / maxVal) * (h - 70)
      }));

      ctx.clearRect(0, 0, w, h);

      // Grid lines
      ctx.strokeStyle = 'rgba(255, 105, 180, 0.12)';
      ctx.lineWidth = 1;
      for (let y = 30; y < h - 30; y += 45) {
        ctx.beginPath();
        ctx.moveTo(35, y);
        ctx.lineTo(w - 20, y);
        ctx.stroke();
      }

      // Gradient under curve
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, 'rgba(255, 42, 112, 0.3)');
      grad.addColorStop(0.6, 'rgba(255, 117, 160, 0.12)');
      grad.addColorStop(1, 'rgba(255, 255, 255, 0.0)');

      ctx.beginPath();
      ctx.moveTo(points[0].x, h - 30);
      ctx.lineTo(points[0].x, points[0].y);
      for (let i = 0; i < points.length - 1; i++) {
        const xc = (points[i].x + points[i + 1].x) / 2;
        const yc = (points[i].y + points[i + 1].y) / 2;
        ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
      }
      ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
      ctx.lineTo(points[points.length - 1].x, h - 30);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Glowing Neon Line
      ctx.save();
      ctx.strokeStyle = '#ff2a70';
      ctx.lineWidth = 3.5;
      ctx.shadowColor = '#ff2a70';
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 0; i < points.length - 1; i++) {
        const xc = (points[i].x + points[i + 1].x) / 2;
        const yc = (points[i].y + points[i + 1].y) / 2;
        ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
      }
      ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
      ctx.stroke();
      ctx.restore();

      // Dots
      points.forEach((p, idx) => {
        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#ff2a70';
        ctx.lineWidth = 2.5;
        ctx.shadowColor = '#ff2a70';
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = '#8c526d';
        ctx.font = '600 10.5px Plus Jakarta Sans';
        ctx.textAlign = 'center';
        ctx.fillText('Kỳ ' + (idx + 1), p.x, h - 12);
      });
    }

    function renderDonutChart() {
      const c = document.getElementById('donut-canvas');
      if (!c) return;
      const rect = c.parentElement.getBoundingClientRect();
      c.width = rect.width;
      c.height = rect.height || 210;
      const ctx = c.getContext('2d');
      const cx = c.width / 2;
      const cy = c.height / 2;
      const r = Math.min(cx, cy) - 22;

      const slices = [
        { label: "Mặt Hàng Dẫn Đầu (38%)", val: 38, color: "#ff2a70" },
        { label: "Nhóm Sản Phẩm Phụ (32%)", val: 32, color: "#ff75a0" },
        { label: "Dịch Vụ & Phụ Kiện (20%)", val: 20, color: "#34d399" },
        { label: "Danh Mục Khác (10%)", val: 10, color: "#fbbf24" }
      ];

      ctx.clearRect(0, 0, c.width, c.height);
      let total = slices.reduce((acc, s) => acc + s.val, 0);
      let curAngle = -Math.PI / 2;

      slices.forEach(s => {
        const sliceAngle = (s.val / total) * (Math.PI * 2);
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, r, curAngle, curAngle + sliceAngle);
        ctx.arc(cx, cy, r * 0.58, curAngle + sliceAngle, curAngle, true);
        ctx.closePath();
        ctx.fillStyle = s.color;
        ctx.shadowColor = s.color;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.restore();
        curAngle += sliceAngle;
      });

      // Center Icon
      ctx.fillStyle = '#ff2a70';
      ctx.font = 'bold 18px Plus Jakarta Sans';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('📊', cx, cy);

      const leg = document.getElementById('donut-legend-row');
      if (leg) {
        leg.innerHTML = slices.map(s => `
          <span style="display:inline-flex; align-items:center; gap:5px;">
            <span style="width:10px; height:10px; border-radius:50%; background:${s.color};"></span>
            ${s.label}
          </span>
        `).join('');
      }
    }

    /* ========================================================
       7. REPORT ACTIONS
    ======================================================== */
    function exportCleanCsv() {
      playChimeSound();
      const data = PRESET_DATA[currentPreset];
      let csvContent = "data:text/csv;charset=utf-8," + "\uFEFF";
      csvContent += data.headers.join(",") + "\r\n";
      data.rows.forEach(r => {
        csvContent += r.map(cell => `"${cell}"`).join(",") + "\r\n";
      });
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", `datalens_report_${currentPreset}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      triggerMagicSparkles(window.innerWidth / 2, 450, 30);
      showToast("✓ Đã tải xuống tệp dữ liệu CSV đã chuẩn hóa!", "📥");
    }

    function copyReportText() {
      playPopSound();
      const text = `
BÁO CÁO PHÂN TÍCH DATALENS STUDIO
==================================
Bộ Dữ Liệu: ${PRESET_DATA[currentPreset].title}
Tổng Doanh Thu: ${PRESET_DATA[currentPreset].metrics.totalRev}
Tổng Số Đơn/Giao Dịch: ${PRESET_DATA[currentPreset].metrics.orders}
Giá Trị Trung Bình (AOV): ${PRESET_DATA[currentPreset].metrics.avgOrder}
Mặt Hàng Dẫn Đầu: ${PRESET_DATA[currentPreset].metrics.bestSeller}
Trạng Thái: Dữ liệu đã được làm sạch và chuẩn hóa 100%, sẵn sàng cho phê duyệt và hoạch định.
      `.trim();
      navigator.clipboard.writeText(text).then(() => {
        triggerMagicSparkles(window.innerWidth / 2, 350, 20);
        showToast("✓ Đã sao chép nội dung báo cáo vào bộ nhớ tạm!", "📋");
      });
    }

    function resetStudioSession() {
      playPopSound();
      if (confirm("Bạn có muốn thiết lập lại phiên làm việc từ đầu không?")) {
        unlockedStep = 1;
        currentStep = 1;
        updateNavigationUI();
        updateViewVisibility();
        selectPreset('bubble_tea');
        showToast("Đã khởi tạo lại phiên làm việc từ Bước 1.", "🔄");
      }
    }

    // INITIALIZE
    window.addEventListener('DOMContentLoaded', () => {
      selectPreset('bubble_tea');
      unlockedStep = 1;
      currentStep = 1;
      updateNavigationUI();
      updateViewVisibility();
    });
  </script>
</body>
</html>
"""

class MinhAnServerHandler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(status=204)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html", "/analysis", "/analysis.html", "/datalens", "/datalens.html"):
            self._set_headers(content_type="text/html")
            analysis_file = os.path.join(BASE_DIR, "analysis.html")
            if os.path.exists(analysis_file):
                with open(analysis_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif path in ("/b2b", "/business", "/customer"):
            self._set_headers(content_type="text/html")
            index_file = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif path in ("/landing", "/landing.html"):
            landing_file = os.path.join(BASE_DIR, "landing.html")
            if os.path.exists(landing_file):
                self._set_headers(content_type="text/html")
                with open(landing_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._set_headers(status=404)
                self.wfile.write(b"Landing page not found")
        elif path == "/diagram":
            diag_file = os.path.join(BASE_DIR, "workflow_diagram.html")
            if os.path.exists(diag_file):
                self._set_headers(content_type="text/html")
                with open(diag_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._set_headers(status=404)
                self.wfile.write(b"Diagram not found")
        elif path == "/diagram.svg":
            svg_file = os.path.join(BASE_DIR, "workflow_diagram.svg")
            if os.path.exists(svg_file):
                self._set_headers(content_type="image/svg+xml")
                with open(svg_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._set_headers(status=404)
                self.wfile.write(b"Diagram SVG not found")
        elif path == "/api/crm_records":
            self._set_headers()
            self.wfile.write(json.dumps(crm_records, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/catalog":
            self._set_headers()
            if os.path.exists(CATALOG_PATH):
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(b"[]")
        elif path == "/api/export_csv":
            csv_lines = [
                "Mã Cơ hội,Khách hàng,Người liên hệ,NVKD Phụ trách,Tổng Niêm Yết,Chiết khấu,Thành tiền,Trạng thái Phê duyệt,Thời gian Triển khai,Checkbox Tạo Báo Giá,Link Docs Báo Giá,Nhận định AI"
            ]
            for r in crm_records:
                warn = r.get("ai_assessment", "").replace('"', '""')
                csv_lines.append(
                    f'"{r["opp_id"]}","{r["customer_name"]}","{r["contact_person"]}","{r["assigned_rep"]}",'
                    f'{r["subtotal"]},{r["discount_pct"]}%,{r["final_total"]},"{r["approval_status"]}",'
                    f'"{r["lead_time_days"]} ngày",{r.get("checkbox_create_quote", False)},"{r.get("quote_doc_url","")}","{warn}"'
                )
            csv_data = "\ufeff" + "\n".join(csv_lines)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=crm_minhan_export.csv")
            self.end_headers()
            self.wfile.write(csv_data.encode("utf-8"))
        else:
            self._set_headers(status=404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def do_POST(self):
        global user_gemini_api_key
        url = urllib.parse.urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        try:
            req_data = json.loads(body) if body else {}
        except Exception:
            req_data = {}

        if path == "/api/customer_chat":
            q = req_data.get("query", "")
            res = call_customer_consultant(q, user_gemini_api_key)
            self._set_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/ai_chat":
            q = req_data.get("query", "")
            context = {"records": crm_records}
            reply = call_gemini_copilot(q, context, user_gemini_api_key)
            self._set_headers()
            self.wfile.write(json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/ai_rewrite_email":
            email_txt = req_data.get("email", "")
            tone = req_data.get("tone", "negotiate")
            rewritten = call_gemini_rewrite_email(email_txt, tone, user_gemini_api_key)
            self._set_headers()
            self.wfile.write(json.dumps({"rewritten": rewritten}, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/process_inquiry":
            extracted = agent.parse_inquiry_agent(req_data)
            opp = agent.validate_and_price_agent(extracted)
            drafts = agent.generate_proposals_and_drafts(opp)

            status = "Chờ Trưởng phòng duyệt" if opp.approval_required else "Đúng thẩm quyền (<=10%)"
            ai_eval = generate_ai_assessment(opp)

            record = {
                "opp_id": opp.opportunity_id,
                "customer_name": opp.customer_name,
                "contact_person": opp.contact_person,
                "email": opp.email,
                "phone": opp.phone,
                "raw_content": req_data.get("raw_content", ""),
                "assigned_rep": f"{opp.assigned_rep_name} ({opp.assigned_rep_id})",
                "rep_email": opp.assigned_rep_email,
                "subtotal": opp.subtotal,
                "discount_pct": opp.discount_pct,
                "discount_amount": opp.discount_amount,
                "final_total": opp.final_total,
                "approval_status": status,
                "lead_time_days": opp.max_lead_time_days,
                "deadline_feasibility": opp.deadline_feasibility,
                "ai_assessment": ai_eval,
                "checkbox_create_quote": False,
                "quote_doc_url": f"https://docs.google.com/document/d/minhan-{opp.opportunity_id.lower()}-official-quote/edit",
                "items": [asdict(i) for i in opp.items],
                "drafts": drafts,
                "created_at": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            crm_records.insert(0, record)
            self._set_headers()
            self.wfile.write(json.dumps(record, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/manager_decision":
            opp_id = req_data.get("opp_id")
            decision = req_data.get("decision")
            target = next((r for r in crm_records if r["opp_id"] == opp_id), None)

            if target:
                if decision == "approve":
                    target["approval_status"] = "Đã duyệt (Trưởng phòng duyệt)"
                elif decision == "reject":
                    target["approval_status"] = "Hoàn tất (Từ chối)"
                    target["checkbox_create_quote"] = False
                self._set_headers()
                self.wfile.write(json.dumps({"success": True, "record": target}, ensure_ascii=False).encode("utf-8"))
            else:
                self._set_headers(status=404)
                self.wfile.write(json.dumps({"error": "Không tìm thấy cơ hội"}, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/trigger_create_quote":
            opp_id = req_data.get("opp_id")
            target = next((r for r in crm_records if r["opp_id"] == opp_id), None)

            if target:
                target["checkbox_create_quote"] = True
                doc_url = f"https://docs.google.com/document/d/minhan-{opp_id.lower()}-official-quote/edit"
                target["quote_doc_url"] = doc_url
                self._set_headers()
                self.wfile.write(json.dumps({"success": True, "doc_url": doc_url}, ensure_ascii=False).encode("utf-8"))
            else:
                self._set_headers(status=404)
                self.wfile.write(json.dumps({"error": "Không tìm thấy cơ hội"}, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/complete_deal":
            opp_id = req_data.get("opp_id")
            target = next((r for r in crm_records if r["opp_id"] == opp_id), None)

            if target:
                target["approval_status"] = "Chốt đơn / Hoàn tất"
                self._set_headers()
                self.wfile.write(json.dumps({"success": True, "record": target}, ensure_ascii=False).encode("utf-8"))
            else:
                self._set_headers(status=404)
                self.wfile.write(json.dumps({"error": "Không tìm thấy cơ hội"}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/clear_all":
            crm_records.clear()
            self._set_headers()
            self.wfile.write(json.dumps({"success": True, "count": 0}, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/load_sample":
            load_sample_crm_data()
            self._set_headers()
            self.wfile.write(json.dumps({"success": True, "records": crm_records}, ensure_ascii=False).encode("utf-8"))

        else:
            self._set_headers(status=404)
            self.wfile.write(json.dumps({"error": "Endpoint không hợp lệ"}).encode("utf-8"))


# Expose WSGI application object for Vercel, Gunicorn, uWSGI, Render, Railway
import wsgi_adapter
import sys
app = wsgi_adapter.create_wsgi_app(sys.modules[__name__])
application = app
handler = MinhAnServerHandler


def run():
    # load_sample_crm_data()  # Khoi dong voi du lieu trong de nguoi dung chu dong nap
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), MinhAnServerHandler) as httpd:
        print("=" * 75)
        print(" CÔNG TY CÔNG NGHỆ MINH AN - B2B AI AGENT STUDIO (DUAL PORTALS)")
        print(f" Web Dashboard (Doanh nghiệp): http://localhost:{PORT}")
        print(f" Cổng Khách hàng (Customer):   http://localhost:{PORT}/customer")
        print(" Đang phục vụ trên cổng 8080...")
        print("=" * 75)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng máy chủ localhost.")


if __name__ == "__main__":
    run()
