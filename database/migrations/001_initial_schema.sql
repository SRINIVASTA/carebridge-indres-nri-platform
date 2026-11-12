-- CareBridge India Initial Schema & Row-Level Security (RLS)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Profile Table (with preferred communication channels)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('NRI', 'CARE_MANAGER', 'ADMIN')),
    phone TEXT NOT NULL,
    whatsapp_number TEXT,
    preferred_channels TEXT[] DEFAULT ARRAY['EMAIL', 'WHATSAPP'],
    country TEXT DEFAULT 'USA',
    preferred_currency TEXT DEFAULT 'USD' CHECK (preferred_currency IN ('USD', 'INR', 'GBP', 'EUR')),
    kyc_verified BOOLEAN DEFAULT FALSE,
    police_clearance_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Parents / Beneficiaries in India
CREATE TABLE IF NOT EXISTS public.parents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nri_user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    age INT NOT NULL CHECK (age >= 45 AND age <= 120),
    city TEXT NOT NULL,
    address TEXT NOT NULL,
    blood_group TEXT,
    emergency_contact_india TEXT,
    medical_conditions TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Subscriptions & Prepaid Expense Wallet
CREATE TABLE IF NOT EXISTS public.wallets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nri_user_id UUID UNIQUE NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    plan_tier TEXT DEFAULT 'PAY_AS_YOU_GO' CHECK (plan_tier IN ('PAY_AS_YOU_GO', 'ESSENTIAL', 'COMPLETE', 'COUPLE')),
    balance_inr NUMERIC(12, 2) DEFAULT 0.00 CHECK (balance_inr >= 0),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Care Tasks & On-Demand Bookings
CREATE TABLE IF NOT EXISTS public.tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nri_user_id UUID NOT NULL REFERENCES public.users(id),
    parent_id UUID NOT NULL REFERENCES public.parents(id),
    care_manager_id UUID REFERENCES public.users(id),
    category TEXT NOT NULL CHECK (category IN ('MEDICAL_ESCORT', 'VITALS_CHECK', 'BANK_GOV_ERRAND', 'AIRPORT_ASSIST', 'PROPERTY_CHECK', 'EMERGENCY_SOS')),
    title TEXT NOT NULL,
    instructions TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'SOS_ACTIVE')),
    gps_lat DOUBLE PRECISION,
    gps_lng DOUBLE PRECISION,
    checkin_time TIMESTAMPTZ,
    service_fee_inr NUMERIC(10, 2) DEFAULT 0.00,
    out_of_pocket_inr NUMERIC(10, 2) DEFAULT 0.00,
    receipt_url TEXT,
    receipt_verified BOOLEAN DEFAULT FALSE,
    completion_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Itemized Invoices & PDF Reports
CREATE TABLE IF NOT EXISTS public.invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_number TEXT UNIQUE NOT NULL,
    nri_user_id UUID NOT NULL REFERENCES public.users(id),
    task_id UUID REFERENCES public.tasks(id),
    currency TEXT NOT NULL DEFAULT 'INR',
    service_fee_inr NUMERIC(10, 2) DEFAULT 0.00,
    out_of_pocket_inr NUMERIC(10, 2) DEFAULT 0.00,
    gst_inr NUMERIC(10, 2) DEFAULT 0.00,
    total_inr NUMERIC(10, 2) NOT NULL,
    total_converted NUMERIC(10, 2) NOT NULL,
    pdf_storage_path TEXT,
    status TEXT DEFAULT 'PAID' CHECK (status IN ('DRAFT', 'ISSUED', 'PAID', 'REFUNDED')),
    dispatched_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Vitals & Encrypted Health Vault Records
CREATE TABLE IF NOT EXISTS public.vitals_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_id UUID NOT NULL REFERENCES public.parents(id) ON DELETE CASCADE,
    logged_by UUID REFERENCES public.users(id),
    systolic_bp INT,
    diastolic_bp INT,
    blood_sugar_mgdl INT,
    pulse_bpm INT,
    spo2_percent INT,
    notes TEXT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.health_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_id UUID NOT NULL REFERENCES public.parents(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES public.users(id),
    doc_type TEXT NOT NULL CHECK (doc_type IN ('PRESCRIPTION', 'LAB_REPORT', 'INSURANCE', 'ID_PROOF', 'INVOICE', 'VISIT_REPORT')),
    title TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row-Level Security (RLS)
ALTER TABLE public.parents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vitals_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_documents ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "NRI view own parents" ON public.parents
    FOR ALL USING (auth.uid() = nri_user_id);

CREATE POLICY "NRI view own wallet" ON public.wallets
    FOR ALL USING (auth.uid() = nri_user_id);

CREATE POLICY "NRI view own invoices" ON public.invoices
    FOR SELECT USING (auth.uid() = nri_user_id);

CREATE POLICY "NRI and assigned Care Manager view tasks" ON public.tasks
    FOR SELECT USING (auth.uid() = nri_user_id OR auth.uid() = care_manager_id);
