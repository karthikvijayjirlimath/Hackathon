import { useParams, Link } from 'react-router-dom'
import { ChevronLeft, FileText, Calendar, Activity, CreditCard, Shield } from 'lucide-react'

const PatientDetail = () => {
  const { id } = useParams()
  
  // Mock data
  const patient = {
    name: 'John Doe',
    external_id: 'P2002',
    dob: '1985-05-20',
    insurance: 'POL-10001',
    bills: [
      { id: 'INV-100010', date: '2025-10-15', amount: 250, status: 'Paid' },
      { id: 'INV-100045', date: '2025-11-20', amount: 1200, status: 'Pending' }
    ],
    records: [
      { type: 'Clinical Report', date: '2025-10-15', summary: 'Initial Diagnosis: Asthma' }
    ]
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex items-center gap-4">
        <Link to="/" className="p-2 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-primary hover:border-primary transition-all shadow-sm">
          <ChevronLeft size={20} />
        </Link>
        <div>
          <h1 className="text-3xl font-black text-slate-900">{patient.name}</h1>
          <p className="text-slate-500 font-medium flex items-center gap-2">
            <Shield size={14} /> ID: {patient.external_id}
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm space-y-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 border-b border-slate-50 pb-3">
              <Activity size={18} className="text-primary" /> Patient Info
            </h3>
            <div className="space-y-4">
              <div>
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Date of Birth</label>
                <p className="font-semibold text-slate-700">{patient.dob}</p>
              </div>
              <div>
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Insurance Policy</label>
                <p className="font-semibold text-slate-700">{patient.insurance}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-slate-50/50 border-b border-slate-100 flex justify-between items-center">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <CreditCard size={18} className="text-blue-500" /> Billing History
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                    <th className="px-6 py-4">Invoice #</th>
                    <th className="px-6 py-4">Date</th>
                    <th className="px-6 py-4">Amount</th>
                    <th className="px-6 py-4 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {patient.bills.map((bill) => (
                    <tr key={bill.id} className="hover:bg-slate-50 transition-colors group">
                      <td className="px-6 py-4 font-bold text-slate-700">{bill.id}</td>
                      <td className="px-6 py-4 text-slate-500 text-sm">{bill.date}</td>
                      <td className="px-6 py-4 font-bold text-slate-900">${bill.amount.toFixed(2)}</td>
                      <td className="px-6 py-4 text-right">
                        <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${
                          bill.status === 'Paid' ? 'bg-emerald-50 text-emerald-600' : 'bg-orange-50 text-orange-600'
                        }`}>
                          {bill.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-slate-50/50 border-b border-slate-100 flex justify-between items-center">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <FileText size={18} className="text-emerald-500" /> Clinical Records
              </h3>
            </div>
            <div className="divide-y divide-slate-100">
              {patient.records.map((record, idx) => (
                <div key={idx} className="p-6 hover:bg-slate-50 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-slate-800">{record.type}</h4>
                    <span className="text-xs text-slate-400 font-medium flex items-center gap-1">
                      <Calendar size={12} /> {record.date}
                    </span>
                  </div>
                  <p className="text-slate-600 text-sm leading-relaxed">{record.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PatientDetail
