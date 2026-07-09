import React, { useState } from 'react';
import { 
  Clock, 
  Award, 
  AlertTriangle, 
  AlertCircle, 
  TrendingUp, 
  RefreshCw,
  Layers,
  ChevronRight
} from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState('NSEIT Certificate');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hoveredMonth, setHoveredMonth] = useState(null);

  // Tabs structure
  const tabs = [
    { id: 'LMS Credentials', label: 'LMS Credentials', count: '45' },
    { id: 'NSEIT Certificate', label: 'NSEIT Certificate', count: '109' },
    { id: 'Operator Activation', label: 'Operator Activation', count: '89' },
    { id: 'Operator Re-activation', label: 'Operator Re-activation', count: '24' },
  ];

  // Month trend data for the 12 Months
  const monthlyData = [
    { month: 'Aug-25', submissions: 42, approvals: 35, rejections: 5 },
    { month: 'Sep-25', submissions: 55, approvals: 45, rejections: 6 },
    { month: 'Oct-25', submissions: 48, approvals: 40, rejections: 4 },
    { month: 'Nov-25', submissions: 60, approvals: 50, rejections: 8 },
    { month: 'Dec-25', submissions: 35, approvals: 30, rejections: 3 },
    { month: 'Jan-26', submissions: 70, approvals: 58, rejections: 7 },
    { month: 'Feb-26', submissions: 82, approvals: 72, rejections: 5 },
    { month: 'Mar-26', submissions: 90, approvals: 80, rejections: 6 },
    { month: 'Apr-26', submissions: 95, approvals: 85, rejections: 4 },
    { month: 'May-26', submissions: 110, approvals: 92, rejections: 10 },
    { month: 'Jun-26', submissions: 105, approvals: 95, rejections: 6 },
    { month: 'Jul-26', submissions: 109, approvals: 95, rejections: 6 },
  ];

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 800);
  };

  // Rendering Active Tab Content
  const renderTabContent = () => {
    if (activeTab !== 'NSEIT Certificate') {
      return (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center bg-white rounded-2xl border border-slate-200/60 shadow-2xs animate-fade-in">
          <div className="p-4 bg-slate-50 text-slate-400 rounded-full mb-4">
            <Layers className="w-10 h-10 stroke-[1.5]" />
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{activeTab} Details</h3>
          <p className="text-sm text-slate-500 max-w-sm mb-6">
            Detailed tracking metrics for {activeTab} are currently being loaded into the admin gateway portal.
          </p>
          <button 
            onClick={() => setActiveTab('NSEIT Certificate')} 
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100/80 rounded-lg transition-all"
          >
            <span>Return to NSEIT Certificate Monitoring</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      );
    }

    return (
      <div className="space-y-6 animate-fade-in">
        {/* KPI Banner */}
        <div className="relative overflow-hidden bg-gradient-to-r from-blue-600 via-blue-700 to-indigo-800 rounded-2xl p-6 shadow-md shadow-blue-900/10">
          <div className="absolute top-0 right-0 w-96 h-96 bg-white/5 rounded-full blur-3xl transform translate-x-1/3 -translate-y-1/3 pointer-events-none"></div>
          <div className="absolute -bottom-10 left-1/3 w-64 h-64 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none"></div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 relative z-10">
            {/* CARD 1 */}
            <div className="group relative overflow-hidden bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 rounded-xl p-5 transition-all duration-300">
              <div className="flex flex-col h-full justify-between">
                <div className="text-3xl font-extrabold text-white tracking-tight mb-2 group-hover:scale-105 transition-transform origin-left">
                  109
                </div>
                <div className="text-[10px] font-bold text-white/70 tracking-widest uppercase mt-auto">
                  TOTAL REQUESTS
                </div>
              </div>
            </div>

            {/* CARD 2 */}
            <div className="group relative overflow-hidden bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 rounded-xl p-5 transition-all duration-300">
              <div className="flex flex-col h-full justify-between">
                <div className="text-3xl font-extrabold text-white tracking-tight mb-2 group-hover:scale-105 transition-transform origin-left">
                  0
                </div>
                <div className="text-[10px] font-bold text-white/70 tracking-widest uppercase mt-auto">
                  PENDING (INTERNAL QUEUE)
                </div>
              </div>
            </div>

            {/* CARD 3 */}
            <div className="group relative overflow-hidden bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 rounded-xl p-5 transition-all duration-300">
              <div className="flex flex-col h-full justify-between">
                <div className="text-3xl font-extrabold text-emerald-400 tracking-tight mb-2 group-hover:scale-105 transition-transform origin-left">
                  95
                </div>
                <div className="text-[10px] font-bold text-white/70 tracking-widest uppercase mt-auto">
                  APPROVED
                </div>
              </div>
            </div>

            {/* CARD 4 */}
            <div className="group relative overflow-hidden bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 rounded-xl p-5 transition-all duration-300">
              <div className="flex flex-col h-full justify-between">
                <div className="text-3xl font-extrabold text-rose-400 tracking-tight mb-2 group-hover:scale-105 transition-transform origin-left">
                  6
                </div>
                <div className="text-[10px] font-bold text-white/70 tracking-widest uppercase mt-auto">
                  REJECTED
                </div>
              </div>
            </div>

            {/* CARD 5 */}
            <div className="group relative overflow-hidden bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 rounded-xl p-5 transition-all duration-300">
              <div className="flex flex-col h-full justify-between">
                <div className="text-3xl font-extrabold text-amber-400 tracking-tight mb-2 group-hover:scale-105 transition-transform origin-left">
                  8
                </div>
                <div className="text-[10px] font-bold text-white/70 tracking-widest uppercase mt-auto">
                  REVERTED
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Mid-Section Operations (50/50 Grid Split) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Left Card: Request Aging Report */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs flex flex-col gap-6 hover:shadow-md hover:border-slate-300/80 transition-all duration-300">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-slate-50 text-slate-500 rounded-lg">
                  <Clock className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 leading-tight">Request Aging Report</h3>
                  <p className="text-[10px] text-slate-400 font-medium mt-0.5">Distribution of pending requests in queue</p>
                </div>
              </div>
              <span className="text-[10px] font-bold text-slate-500 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-md">Pending Items</span>
            </div>

            <div className="space-y-4">
              {/* 0-3 Days */}
              <div className="flex items-center justify-between gap-4 group">
                <span className="text-[10px] font-bold text-slate-500 bg-slate-50 border border-slate-100/80 px-2 py-1 rounded-md w-16 text-center select-none">0-3 Days</span>
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden relative">
                  <div 
                    className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all duration-500 shadow-[0_1px_2px_rgba(16,185,129,0.2)]" 
                    style={{ width: '60%' }}
                  />
                </div>
                <span className="text-xs font-bold text-slate-700 w-20 text-right">45 Requests</span>
              </div>

              {/* 4-7 Days */}
              <div className="flex items-center justify-between gap-4 group">
                <span className="text-[10px] font-bold text-slate-500 bg-slate-50 border border-slate-100/80 px-2 py-1 rounded-md w-16 text-center select-none">4-7 Days</span>
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden relative">
                  <div 
                    className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-amber-400 to-yellow-500 transition-all duration-500 shadow-[0_1px_2px_rgba(245,158,11,0.2)]" 
                    style={{ width: '25%' }}
                  />
                </div>
                <span className="text-xs font-bold text-slate-700 w-20 text-right">18 Requests</span>
              </div>

              {/* 8-15 Days */}
              <div className="flex items-center justify-between gap-4 group">
                <span className="text-[10px] font-bold text-slate-500 bg-slate-50 border border-slate-100/80 px-2 py-1 rounded-md w-16 text-center select-none">8-15 Days</span>
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden relative">
                  <div 
                    className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-orange-400 to-orange-500 transition-all duration-500 shadow-[0_1px_2px_rgba(249,115,22,0.2)]" 
                    style={{ width: '11%' }}
                  />
                </div>
                <span className="text-xs font-bold text-slate-700 w-20 text-right">8 Requests</span>
              </div>

              {/* 15+ Days */}
              <div className="flex items-center justify-between gap-4 group">
                <span className="text-[10px] font-bold text-rose-500 bg-rose-50 border border-rose-100/40 px-2 py-1 rounded-md w-16 text-center select-none">15+ Days</span>
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden relative">
                  <div 
                    className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-rose-500 to-red-600 transition-all duration-500 shadow-[0_1px_2px_rgba(239,68,68,0.2)]" 
                    style={{ width: '5%' }}
                  />
                </div>
                <span className="text-xs font-extrabold text-rose-600 w-20 text-right flex items-center justify-end gap-1.5">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-red-600"></span>
                  </span>
                  3 Requests
                </span>
              </div>
            </div>
          </div>

          {/* Right Card: Health Tracker */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs flex flex-col gap-6 hover:shadow-md hover:border-slate-300/80 transition-all duration-300">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-slate-50 text-slate-500 rounded-lg">
                  <Award className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 leading-tight">NSEIT Certificate Health Tracker</h3>
                  <p className="text-[10px] text-slate-400 font-medium mt-0.5">Real-time gateway credentials health status</p>
                </div>
              </div>
              <span className="text-[10px] font-bold text-rose-500 bg-rose-50 border border-rose-100/50 px-2 py-0.5 rounded-md">Gateway Monitor</span>
            </div>

            <div className="flex flex-col gap-3">
              {/* Amber – expiring soon */}
              <div className="bg-gradient-to-r from-amber-50/80 to-amber-50 border border-amber-200/60 rounded-xl p-4 flex items-center gap-3 hover:shadow-xs transition-all">
                <div className="p-1.5 bg-amber-100 text-amber-600 rounded-lg">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <h4 className="text-xs font-bold text-amber-950 flex items-center gap-1.5">
                  <span className="text-sm font-extrabold text-amber-600">14</span>
                  <span>Certificates Expiring within 30 days</span>
                </h4>
              </div>

              {/* Red – already expired */}
              <div className="bg-gradient-to-r from-rose-50/80 to-rose-50 border border-rose-200/60 rounded-xl p-4 flex items-center gap-3 hover:shadow-xs transition-all">
                <div className="p-1.5 bg-rose-100 text-rose-600 rounded-lg">
                  <AlertCircle className="w-4 h-4" />
                </div>
                <h4 className="text-xs font-bold text-rose-950 flex items-center gap-1.5">
                  <span className="text-sm font-extrabold text-rose-600">5</span>
                  <span>Already Expired (Blocked Status)</span>
                </h4>
              </div>
            </div>
          </div>

        </div>



      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50/60 p-4 md:p-6 text-slate-800 font-sans">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Typography Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Operator Requests Overview
          </h1>
          <button 
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="self-start sm:self-center flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-slate-600 bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 shadow-2xs rounded-lg transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        {/* Segmented Sub-Navigation (Full Width below Title) */}
        <div className="bg-slate-100/80 p-1.5 rounded-xl border border-slate-200/40 shadow-xs">
          <nav className="grid grid-cols-2 md:grid-cols-4 gap-1 w-full" aria-label="Sub Navigation">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full py-2.5 px-3 text-xs font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer
                    ${isActive 
                      ? 'bg-white text-slate-900 font-semibold shadow-xs' 
                      : 'text-slate-500 hover:text-slate-700 hover:bg-white/40'}`}
                >
                  <span>{tab.label}</span>
                  {tab.count && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${isActive ? 'bg-slate-100 text-slate-800' : 'bg-slate-200/50 text-slate-600'}`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab content panel */}
        {renderTabContent()}

      </div>
    </div>
  );
}

export default App;
